from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import yt_dlp
import tempfile
import os
import time
import zipfile
import io
import shutil

app = FastAPI(
    title="TikTok Downloader API",
    version="1.0.0"
)

# =====================================================
# MODELS
# =====================================================

class VideoRequest(BaseModel):
    url: str
    quality: str = "best"   # best | 720p | 480p

class ProfileRequest(BaseModel):
    profile_url: str
    sleep_seconds: int = 2  # anti-block delay

class ZipRequest(BaseModel):
    urls: List[str]
    quality: str = "best"

# =====================================================
# HELPERS
# =====================================================

def select_format(quality: str) -> str:
    if quality == "720p":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    if quality == "480p":
        return "bestvideo[height<=480]+bestaudio/best[height<=480]"
    return "best"

def safe_cleanup(path: str):
    try:
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

# =====================================================
# HEALTH CHECK
# =====================================================

@app.get("/")
def health():
    return {
        "status": "backend running",
        "service": "tiktok-downloader",
        "version": "1.0.0"
    }

# =====================================================
# SINGLE VIDEO DOWNLOAD (STREAMED)
# =====================================================

@app.post("/video")
def download_video(data: VideoRequest):
    temp_dir = tempfile.mkdtemp()

    try:
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
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    yield chunk
            safe_cleanup(temp_dir)

        return StreamingResponse(
            stream_file(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
            }
        )

    except Exception as e:
        safe_cleanup(temp_dir)
        raise HTTPException(status_code=400, detail=str(e))

# =====================================================
# PROFILE — SCRAPE ALL VIDEOS (NO PAGINATION)
# =====================================================

@app.post("/profile/all")
def scrape_all_profile_videos(data: ProfileRequest):
    """
    Returns ALL video URLs from a TikTok profile.
    No UI limits. No pagination. Frontend decides how to render.
    """

    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        entries = info.get("entries", [])
        videos = []

        for entry in entries:
            if entry.get("url"):
                videos.append(entry["url"])
                if data.sleep_seconds > 0:
                    time.sleep(data.sleep_seconds)

        return {
            "profile_url": data.profile_url,
            "total_videos": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =====================================================
# BULK ZIP DOWNLOAD (STREAMED)
# =====================================================

@app.post("/zip")
def zip_download(data: ZipRequest):
    """
    Downloads multiple TikTok videos and returns a ZIP file.
    """

    temp_root = tempfile.mkdtemp()
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, url in enumerate(data.urls, start=1):
                temp_dir = tempfile.mkdtemp(dir=temp_root)

                ydl_opts = {
                    "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
                    "format": select_format(data.quality),
                    "merge_output_format": "mp4",
                    "noplaylist": True,
                    "quiet": True
                }

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)

                    if os.path.exists(filename):
                        zf.write(
                            filename,
                            arcname=f"{idx}_{os.path.basename(filename)}"
                        )

                except Exception:
                    pass  # skip failed videos

                finally:
                    safe_cleanup(temp_dir)

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=tiktok_videos.zip"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        safe_cleanup(temp_root)
