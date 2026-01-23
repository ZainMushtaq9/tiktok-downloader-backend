from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os
import subprocess

app = FastAPI()

# =========================
# MODELS
# =========================

class ProfileRequest(BaseModel):
    profile_url: str

class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"  # best | 720p | 480p


# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "backend running"}


# =========================
# SCRAPE PROFILE (ALL VIDEOS)
# =========================

@app.post("/profile/all")
def scrape_profile(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = [
            entry["url"]
            for entry in info.get("entries", [])
            if entry.get("url")
        ]

        return {
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# DOWNLOAD + AUTO BLACK & WHITE
# =========================

@app.post("/download")
def download_video(data: DownloadRequest):
    tmp = tempfile.mkdtemp()

    raw = os.path.join(tmp, "raw.mp4")
    final = os.path.join(tmp, "final.mp4")

    try:
        # -------------------------
        # QUALITY
        # -------------------------
        if data.quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        elif data.quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best"
        else:
            fmt = "best"

        # -------------------------
        # DOWNLOAD
        # -------------------------
        ydl_opts = {
            "outtmpl": raw,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([data.url])

        if not os.path.exists(raw):
            raise Exception("Download failed")

        # -------------------------
        # APPLY BLACK & WHITE
        # -------------------------
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", raw,
                "-vf", "format=gray",
                "-c:a", "copy",
                final
            ],
            check=True
        )

        # -------------------------
        # STREAM
        # -------------------------
        def stream():
            with open(final, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

            # cleanup
            try:
                os.remove(raw)
                os.remove(final)
                os.rmdir(tmp)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": "attachment; filename=video_bw.mp4"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
