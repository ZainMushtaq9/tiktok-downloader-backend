from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os
import zipfile
import io
import shutil
from typing import List

app = FastAPI()

# =========================
# MODELS
# =========================

class ZipDownloadRequest(BaseModel):
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
# ZIP DOWNLOAD (ONE FILE)
# =========================

@app.post("/download/zip")
def download_zip(data: ZipDownloadRequest):
    temp_root = tempfile.mkdtemp()
    zip_buffer = io.BytesIO()

    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
            for idx, url in enumerate(data.urls, start=1):
                tmp_dir = tempfile.mkdtemp(dir=temp_root)

                ydl_opts = {
                    "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
                    "format": select_format(data.quality),
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "noplaylist": True,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    file_path = ydl.prepare_filename(info)

                if os.path.exists(file_path):
                    zipf.write(
                        file_path,
                        arcname=f"{idx}.mp4"
                    )

                shutil.rmtree(tmp_dir, ignore_errors=True)

        zip_buffer.seek(0)

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="videos.zip"'
            }
        )

    except Exception as e:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
