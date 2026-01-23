from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os

app = FastAPI()

class ProfileRequest(BaseModel):
    profile_url: str

class VideoRequest(BaseModel):
    url: str
    quality: str = "best"


@app.get("/")
def health():
    return {"status": "backend running"}


# =========================
# SCRAPE PROFILE
# =========================

@app.post("/profile/all")
def scrape_all_videos(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = [e["url"] for e in info.get("entries", []) if e.get("url")]

        return {"total": len(videos), "videos": videos}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# PREVIEW (STREAMABLE URL)
# =========================

@app.post("/preview")
def preview_video(data: VideoRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=False)

        # Best playable URL
        video_url = info.get("url")

        if not video_url:
            raise Exception("No playable stream found")

        return {"preview_url": video_url}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# DOWNLOAD (STREAM FILE)
# =========================

@app.post("/download")
def download_video(data: VideoRequest):
    try:
        tmp = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": f"{tmp}/%(id)s.%(ext)s",
            "format": data.quality,
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
            os.remove(filename)
            os.rmdir(tmp)

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
