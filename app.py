from fastapi import FastAPI, HTTPException
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
# CORS (MANDATORY)
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
# HEALTH
# =========================
@app.get("/")
def health():
    return {"status": "ok"}

# =========================
# STREAM PROFILE (ASYNC)
# =========================
@app.post("/profile/stream")
async def stream_profile(data: ProfileRequest):

    async def event_stream():
        # Send immediate heartbeat
        yield json.dumps({"status": "starting"}) + "\n"
        await asyncio.sleep(0.1)

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
                payload = {
                    "current": idx,
                    "total": total,
                    "url": entry.get("url")
                }
                yield json.dumps(payload) + "\n"

                # tiny async yield so Railway flushes
                await asyncio.sleep(0.01)

        except Exception as e:
            yield json.dumps({"error": str(e)}) + "\n"

    return StreamingResponse(event_stream(), media_type="text/plain")

# =========================
# SINGLE VIDEO DOWNLOAD
# =========================
@app.get("/download")
def download_video(url: str, n: int):
    try:
        tmp = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": os.path.join(tmp, f"{n}.%(ext)s"),
            "format": "best",
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        def stream_file():
            with open(filename, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(filename)
                os.rmdir(tmp)
            except:
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
