from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os
import subprocess
from typing import List, Optional

app = FastAPI()

# =========================
# MODELS
# =========================

class ProfileRequest(BaseModel):
    profile_url: str

class DownloadRequest(BaseModel):
    url: str
    quality: str = "best"          # best | 720p | 480p
    filter: str = "original"       # original | bw
    urdu_caption: Optional[str] = None


# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def health():
    return {"status": "backend running"}


# =========================
# SCRAPE ALL VIDEOS FROM PROFILE
# =========================

@app.post("/profile/all")
def scrape_all_videos(data: ProfileRequest):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True,
            "forcejson": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)

        videos = []
        for entry in info.get("entries", []):
            if entry.get("url"):
                videos.append(entry["url"])

        return {
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# =========================
# DOWNLOAD SINGLE VIDEO
# (FILTER + URDU TEXT OPTIONAL)
# =========================

@app.post("/download")
def download_video(data: DownloadRequest):
    tmp_dir = tempfile.mkdtemp()
    raw_video = os.path.join(tmp_dir, "raw.mp4")
    final_video = os.path.join(tmp_dir, "final.mp4")

    try:
        # -------------------------
        # QUALITY SELECTOR
        # -------------------------
        if data.quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif data.quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best[height<=480]"
        else:
            fmt = "best"

        # -------------------------
        # DOWNLOAD VIDEO
        # -------------------------
        ydl_opts = {
            "outtmpl": raw_video,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([data.url])

        if not os.path.exists(raw_video):
            raise Exception("Video download failed")

        # -------------------------
        # BUILD FFMPEG FILTERS
        # -------------------------
        filters = []

        if data.filter == "bw":
            filters.append("format=gray")

        if data.urdu_caption:
            caption = data.urdu_caption.replace("'", "’")
            filters.append(
                f"drawtext=text='{caption}':"
                f"fontcolor=white:fontsize=36:"
                f"x=(w-text_w)/2:y=h-80:"
                f"box=1:boxcolor=black@0.6"
            )

        filter_chain = ",".join(filters)

        # -------------------------
        # PROCESS VIDEO
        # -------------------------
        if filter_chain:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", raw_video,
                    "-vf", filter_chain,
                    "-c:a", "copy",
                    final_video
                ],
                check=True
            )
        else:
            os.rename(raw_video, final_video)

        # -------------------------
        # STREAM TO CLIENT
        # -------------------------
        def stream():
            with open(final_video, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

            # Cleanup
            try:
                os.remove(final_video)
                if os.path.exists(raw_video):
                    os.remove(raw_video)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": "attachment; filename=video.mp4"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
