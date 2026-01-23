from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import json
import tempfile
import os
import asyncio

app = FastAPI()

# =========================
# CORS (MANDATORY FOR GITHUB PAGES)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# MODELS
# =========================
class ProfileRequest(BaseModel):
    profile_url: str

# =========================
# HEALTH CHECK
# =========================
@app.get("/")
def health():
    return {"status": "backend running"}

# =========================
# STREAM PROFILE VIDEOS
# =========================
# Streams newline-delimited JSON:
# { current, total, url }
# =========================
@app.post("/profile/stream")
async def profile_stream(data: ProfileRequest):

    async def generator():
        # Small heartbeat so browser sees response immediately
        yield json.dumps({"status": "starting"}) + "\n"
        await asyncio.sleep(0.05)

        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(data.profile_url, download=False)

            entries = info.get("entries", [])
            total = len(entries)

            if total == 0:
                yield json.dumps({"error": "No videos found"}) + "\n"
                return

            for idx, entry in enumerate(entries, start=1):
                video_url = entry.get("url")
                if not video_url:
                    continue

                payload = {
                    "current": idx,
                    "total": total,
                    "url": video_url
                }

                yield json.dumps(payload) + "\n"

                # Tiny async pause to flush stream on Railway
                await asyncio.sleep(0.01)

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(generator(), media_type="text/plain")

# =========================
# SINGLE VIDEO DOWNLOAD
# =========================
# Streams ONE file only (mobile safe)
# =========================
@app.get("/download")
def download_video(
    url: str = Query(...),
    n: int = Query(...)
):
    try:
        temp_dir = tempfile.mkdtemp()
        out_template = os.path.join(temp_dir, f"{n}.%(ext)s")

        ydl_opts = {
            "outtmpl": out_template,
            "format": "best",
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("Video download failed")

        def stream_file():
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1 MB
                    if not chunk:
                        break
                    yield chunk

            # Cleanup
            try:
                os.remove(filename)
                os.rmdir(temp_dir)
            except Exception:
                pass

        return StreamingResponse(
            stream_file(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{n}.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
