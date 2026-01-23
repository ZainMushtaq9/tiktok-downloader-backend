from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os
import shutil

app = FastAPI()

# =========================
# MODELS
# =========================

class ProfileRequest(BaseModel):
    profile_url: str

class DownloadRequest(BaseModel):
    url: str
    index: int
    quality: str = "best"

# =========================
# HELPERS
# =========================

def select_format(quality: str):
    if quality == "720p":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    if quality == "480p":
        return "bestvideo[height<=480]+bestaudio/best[height<=480]"
    return "best"

# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "backend running"}

# =========================
# FETCH ALL PROFILE VIDEOS
# =========================

@app.post("/profile/all")
def fetch_all_profile_videos(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        entries = info.get("entries", [])
        videos = []

        for e in entries:
            if e.get("url"):
                videos.append(e["url"])

        return {
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =========================
# DOWNLOAD SINGLE VIDEO
# =========================

@app.post("/download")
def download_video(data: DownloadRequest):
    tmp_dir = tempfile.mkdtemp()

    try:
        ydl_opts = {
            "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
            "format": select_format(data.quality),
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)
            file_path = ydl.prepare_filename(info)

        if not os.path.exists(file_path):
            raise Exception("Download failed")

        output_name = f"{data.index}.mp4"

        def stream():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{output_name}"'
            }
        )

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
