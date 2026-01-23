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

class DownloadRequest(BaseModel):
    url: str
    index: int
    quality: str = "best"   # best | 720p | 480p

# =========================
# HELPERS
# =========================

def select_format(quality: str) -> str:
    if quality == "720p":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    if quality == "480p":
        return "bestvideo[height<=480]+bestaudio/best[height<=480]"
    return "best"

# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def health():
    return {"status": "backend running"}

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
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)
            file_path = ydl.prepare_filename(info)

        if not os.path.exists(file_path):
            raise Exception("Video download failed")

        output_name = f"{data.index}.mp4"

        def stream_file():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    yield chunk

            # cleanup after stream
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return StreamingResponse(
            stream_file(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{output_name}"'
            }
        )

    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e))
