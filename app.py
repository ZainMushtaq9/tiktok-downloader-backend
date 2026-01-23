from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os
import time
import zipfile
import io
from typing import List

app = FastAPI()

# =========================
# MODELS
# =========================

class VideoRequest(BaseModel):
    url: str
    quality: str = "best"   # best | 720p | 480p

class ProfileRequest(BaseModel):
    profile_url: str
    offset: int = 0
    limit: int = 10
    sleep_seconds: int = 3

class ProfileCountRequest(BaseModel):
    profile_url: str

class ZipRequest(BaseModel):
    urls: List[str]
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
# SINGLE VIDEO DOWNLOAD
# =========================

@app.post("/resolve")
def download_video(data: VideoRequest):
    try:
        temp_dir = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
            "format": select_format(data.quality),
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)
            filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("Video download failed")

        def stream_file():
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(filename)
                os.rmdir(temp_dir)
            except Exception:
                pass

        return StreamingResponse(
            stream_file(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =========================
# PROFILE VIDEO COUNT
# =========================

@app.post("/profile_count")
def profile_video_count(data: ProfileCountRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        entries = info.get("entries", [])

        return {
            "profile_url": data.profile_url,
            "total_videos": len(entries)
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =========================
# PROFILE SCRAPER (PAGINATED + SLEEP)
# =========================

@app.post("/profile")
def scrape_profile(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
            "playliststart": data.offset + 1,
            "playlistend": data.offset + data.limit
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = []
        for entry in info.get("entries", []):
            if entry.get("url"):
                videos.append(entry["url"])

        # Sleep to reduce blocking
        time.sleep(data.sleep_seconds)

        return {
            "offset": data.offset + len(videos),
            "count": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =========================
# ZIP DOWNLOAD (SELECTED)
# =========================

@app.post("/zip")
def zip_download(data: ZipRequest):
    try:
        mem_zip = io.BytesIO()

        with zipfile.ZipFile(mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for url in data.urls:
                temp_dir = tempfile.mkdtemp()

                ydl_opts = {
                    "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
                    "format": select_format(data.quality),
                    "merge_output_format": "mp4",
                    "noplaylist": True,
                    "quiet": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)

                if os.path.exists(filename):
                    zf.write(filename, arcname=os.path.basename(filename))

                try:
                    os.remove(filename)
                    os.rmdir(temp_dir)
                except Exception:
                    pass

        mem_zip.seek(0)

        return StreamingResponse(
            mem_zip,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="videos.zip"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
