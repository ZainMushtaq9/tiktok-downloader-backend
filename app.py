from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os
from typing import List

app = FastAPI()


# =========================
# MODELS
# =========================

class ProfileRequest(BaseModel):
    profile_url: str

class VideoDownloadRequest(BaseModel):
    url: str
    quality: str = "best"


# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "backend running"}


# =========================
# SCRAPE ALL VIDEOS FROM PROFILE
# =========================

@app.post("/profile/all")
def scrape_all_videos(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = []
        for entry in info.get("entries", []):
            if entry.get("url"):
                videos.append(entry["url"])

        return {
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# DOWNLOAD SINGLE VIDEO (STREAMED)
# =========================

@app.post("/download")
def download_video(data: VideoDownloadRequest):
    try:
        temp_dir = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
            "format": data.quality,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("Download failed")

        def stream():
            with open(filename, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(filename)
                os.rmdir(temp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
