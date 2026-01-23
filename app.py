from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re
import time

app = FastAPI()

def clean_name(text):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/profile")
def profile(profile_url: str):
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(profile_url, download=False)

    profile = clean_name(info.get("uploader", "tiktok_profile"))
    videos = [e["url"] for e in info["entries"] if e.get("url")]

    return {
        "profile": profile,
        "total": len(videos),
        "videos": videos
    }

@app.get("/download")
def download(url: str, index: int, profile: str, quality: str = "best"):
    tmp = tempfile.mkdtemp()
    filename = f"{index}.mp4"
    path = os.path.join(tmp, filename)

    ydl_opts = {
        "outtmpl": path,
        "format": quality,
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Download failed")

    def stream():
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk
        try:
            os.remove(path)
            os.rmdir(tmp)
        except:
            pass

    return StreamingResponse(
        stream(),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{profile}_{index}.mp4"'
        }
    )
