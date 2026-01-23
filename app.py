from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import json
import os
import tempfile

app = FastAPI()


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
# This endpoint streams progress line-by-line
# Frontend reads it and updates progress bar
# =========================

@app.post("/profile/stream")
def stream_profile(data: ProfileRequest):

    def generator():
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)
            entries = info.get("entries", [])

            total = len(entries)

            for idx, entry in enumerate(entries, start=1):
                video_url = entry.get("url")

                payload = {
                    "current": idx,
                    "total": total,
                    "url": video_url
                }

                # Send progress update
                yield json.dumps(payload) + "\n"

    return StreamingResponse(generator(), media_type="text/plain")


# =========================
# SINGLE VIDEO DOWNLOAD
# =========================
# Browser will call this repeatedly (one-by-one)
# Minimal RAM usage, streaming file
# =========================

@app.get("/download")
def download_video(
    url: str = Query(...),
    n: int = Query(...)
):
    try:
        temp_dir = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, f"{n}.%(ext)s"),
            "format": "best",
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("Download failed")

        def file_stream():
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB
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
            file_stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{n}.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
