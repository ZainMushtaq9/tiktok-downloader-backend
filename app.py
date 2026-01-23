from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os

app = FastAPI()

class ProfileRequest(BaseModel):
    profile_url: str

class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"
    mode: str = "original"  # original | bw

@app.get("/")
def health():
    return {"status": "backend running"}

@app.get("/profile/all")
def profile_all(profile_url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)

        videos = [
            e["url"] for e in info.get("entries", [])
            if e.get("url")
        ]

        return {"total": len(videos), "videos": videos}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/download")
def download(url: str, quality: str = "best", mode: str = "original"):
    """
    NOTE:
    mode='bw' is accepted for UI compatibility,
    but actual B&W processing is NOT applied (no ffmpeg).
    """

    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, "%(id)s.%(ext)s")

    try:
        if quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        elif quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best"
        else:
            fmt = "best"

        ydl_opts = {
            "outtmpl": out,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

        def stream():
            with open(filename, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(filename)
                os.rmdir(tmp)
            except:
                pass

        name = os.path.basename(filename)
        if mode == "bw":
            name = "BW_" + name  # label only, no transform

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{name}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
