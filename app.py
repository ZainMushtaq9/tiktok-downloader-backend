from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(title="Universal Downloader API")

# ======================================================
# CORS (GitHub Pages / Static Frontend)
# ======================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# HELPERS
# ======================================================

def clean_name(text: str):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "video")

def select_format(quality: str):
    if quality == "720p":
        return "bestvideo[height<=720]+bestaudio/best"
    if quality == "480p":
        return "bestvideo[height<=480]+bestaudio/best"
    return "best"

# ======================================================
# HEALTH CHECK
# ======================================================

@app.get("/")
def health():
    return {"status": "ok"}

# ======================================================
# YOUTUBE INFO (SINGLE / PLAYLIST DETECTION)
# ======================================================

@app.get("/youtube/info")
def youtube_info(url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Playlist
        if info.get("_type") == "playlist":
            return {
                "type": "playlist",
                "title": info.get("title"),
                "total": len(info.get("entries", []))
            }

        # Single video
        return {
            "type": "single",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail")
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ======================================================
# YOUTUBE PLAYLIST VIDEOS (LINK EXPORT ONLY)
# ======================================================

@app.get("/youtube/playlist")
def youtube_playlist(url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        videos = []
        for i, e in enumerate(info.get("entries", []), start=1):
            if e.get("url"):
                videos.append({
                    "index": i,
                    "url": e["url"],
                    "title": e.get("title"),
                    "thumbnail": e.get("thumbnail")
                })

        return {
            "playlist": info.get("title"),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ======================================================
# UNIVERSAL DOWNLOAD ENDPOINT
# (TikTok, YouTube, Instagram, Facebook, Likee)
# ======================================================

@app.get("/download")
def download_video(
    url: str,
    index: int = 1,
    profile: str = "video",
    quality: str = "best"
):
    tmp_dir = tempfile.mkdtemp()
    filename = f"{clean_name(profile)}_{index:03d}.mp4"
    filepath = os.path.join(tmp_dir, filename)

    try:
        ydl_opts = {
            "outtmpl": filepath,
            "format": select_format(quality),
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filepath):
            raise Exception("Download failed")

        def stream():
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(filepath)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
