from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os

app = FastAPI()

class VideoRequest(BaseModel):
    url: str

class ProfileRequest(BaseModel):
    profile_url: str
    limit: int = 5   # SAFE DEFAULT

@app.get("/")
def root():
    return {"status": "backend running"}

# -------- SINGLE VIDEO DOWNLOAD --------

@app.post("/resolve")
def resolve_video(data: VideoRequest):
    try:
        temp_dir = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
            "format": "mp4",
            "noplaylist": True,
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)

        filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("Video not downloaded")

        def stream():
            with open(filename, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(filename)
                os.rmdir(temp_dir)
            except Exception:
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

# -------- PROFILE SCRAPER (SAFE MODE) --------

@app.post("/profile")
def scrape_profile(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
            "playlistend": data.limit
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = []

        for entry in info.get("entries", []):
            if entry.get("url"):
                videos.append(entry["url"])

        return {
            "count": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
