from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os

app = FastAPI()


# ======================
# MODELS
# ======================

class ProfileRequest(BaseModel):
    profile_url: str

class VideoRequest(BaseModel):
    url: str
    quality: str = "best"


# ======================
# HEALTH
# ======================

@app.get("/")
def health():
    return {"status": "ok"}


# ======================
# FETCH ALL VIDEOS
# ======================

@app.post("/profile/all")
def fetch_all_videos(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = []
        for e in info.get("entries", []):
            if e.get("url"):
                videos.append(e["url"])

        return {
            "count": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ======================
# DOWNLOAD SINGLE VIDEO
# ======================

@app.post("/download")
def download_video(data: VideoRequest):
    try:
        tmp = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": f"{tmp}/%(id)s.%(ext)s",
            "format": data.quality,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)
            file_path = ydl.prepare_filename(info)

        if not os.path.exists(file_path):
            raise Exception("Download failed")

        def stream():
            with open(file_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(file_path)
                os.rmdir(tmp)
            except Exception:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(file_path)}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
