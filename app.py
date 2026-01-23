from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import yt_dlp
import tempfile
import os
import zipfile
import io
import shutil

app = FastAPI(title="TikTok Downloader API")

# =========================
# MODELS
# =========================

class VideoRequest(BaseModel):
    url: str
    quality: str = "best"

class ProfileChunkRequest(BaseModel):
    profile_url: str
    offset: int = 0
    limit: int = 20

class ZipRequest(BaseModel):
    urls: List[str]
    quality: str = "best"

# =========================
# HELPERS
# =========================

def select_format(q: str):
    if q == "720p":
        return "bestvideo[height<=720]+bestaudio/best"
    if q == "480p":
        return "bestvideo[height<=480]+bestaudio/best"
    return "best"

def safe_rm(path):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass

# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "ok"}

# =========================
# SINGLE VIDEO
# =========================

@app.post("/video")
def download_video(data: VideoRequest):
    tmp = tempfile.mkdtemp()
    try:
        ydl_opts = {
            "outtmpl": f"{tmp}/%(id)s.%(ext)s",
            "format": select_format(data.quality),
            "merge_output_format": "mp4",
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)
            filename = ydl.prepare_filename(info)

        def stream():
            with open(filename, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            safe_rm(tmp)

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
            }
        )

    except Exception as e:
        safe_rm(tmp)
        raise HTTPException(400, str(e))

# =========================
# PROFILE (CHUNKED SCRAPE)
# =========================

@app.post("/profile/chunk")
def scrape_profile_chunk(data: ProfileChunkRequest):
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

        entries = info.get("entries", [])
        urls = [e["url"] for e in entries if e.get("url")]

        return {
            "offset": data.offset + len(urls),
            "count": len(urls),
            "videos": urls
        }

    except Exception as e:
        raise HTTPException(400, str(e))

# =========================
# ZIP DOWNLOAD
# =========================

@app.post("/zip")
def zip_download(data: ZipRequest):
    tmp_root = tempfile.mkdtemp()
    zip_buf = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, url in enumerate(data.urls, 1):
                tmp = tempfile.mkdtemp(dir=tmp_root)
                ydl_opts = {
                    "outtmpl": f"{tmp}/%(id)s.%(ext)s",
                    "format": select_format(data.quality),
                    "merge_output_format": "mp4",
                    "quiet": True
                }

                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        file = ydl.prepare_filename(info)

                    if os.path.exists(file):
                        zf.write(file, arcname=f"{i}_{os.path.basename(file)}")

                except Exception:
                    pass

                finally:
                    safe_rm(tmp)

        zip_buf.seek(0)
        return StreamingResponse(
            zip_buf,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=videos.zip"}
        )

    except Exception as e:
        raise HTTPException(400, str(e))

    finally:
        safe_rm(tmp_root)
