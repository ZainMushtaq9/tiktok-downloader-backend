from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
import yt_dlp
import tempfile
import os
import re

app = FastAPI()

# ======================================================
# CORS (Required for GitHub Pages / Static Frontend)
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

def clean_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "")

def detect_platform(url: str) -> str:
    domain = urlparse(url).netloc.lower()

    if "tiktok.com" in domain:
        return "tiktok"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "youtube"
    if "instagram.com" in domain:
        return "instagram"
    if "facebook.com" in domain or "fb.watch" in domain:
        return "facebook"
    if "twitter.com" in domain or "x.com" in domain:
        return "twitter"
    if "likee.video" in domain:
        return "likee"

    return "unknown"

def get_format(quality: str) -> str:
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
    return {
        "status": "ok",
        "service": "universal-video-downloader",
        "engine": "yt-dlp"
    }

# ======================================================
# INFO / PREVIEW (ALL PLATFORMS)
# ======================================================

@app.get("/info")
def video_info(url: str):
    """
    Preview-only endpoint.
    No download.
    Safe for AdSense.
    """
    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid URL")

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "platform": detect_platform(url),
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader") or info.get("channel"),
            "webpage_url": info.get("webpage_url") or url,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ======================================================
# YOUTUBE INFO (DETECT SINGLE VS PLAYLIST)
# ======================================================

@app.get("/youtube/info")
def youtube_info(url: str):
    """
    Detects whether the URL is:
    - Single YouTube video
    - YouTube playlist
    """
    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid URL")

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if "entries" in info:
            return {
                "platform": "youtube",
                "type": "playlist",
                "title": info.get("title"),
                "total": len(info.get("entries", [])),
            }

        return {
            "platform": "youtube",
            "type": "single",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ======================================================
# YOUTUBE PLAYLIST (EXPORT VIDEO LINKS ONLY)
# ======================================================

@app.get("/youtube/playlist")
def youtube_playlist(url: str):
    """
    Extracts ALL video URLs from a playlist.
    Does NOT download.
    Frontend controls queue + delay.
    """
    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid playlist URL")

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if "entries" not in info:
            raise HTTPException(status_code=400, detail="Not a playlist")

        videos = []
        for i, entry in enumerate(info["entries"], start=1):
            if not entry:
                continue

            vid = entry.get("url")
            if not vid:
                continue

            if not vid.startswith("http"):
                vid = f"https://www.youtube.com/watch?v={vid}"

            videos.append({
                "index": i,
                "url": vid,
                "title": entry.get("title"),
                "thumbnail": entry.get("thumbnail"),
            })

        return {
            "platform": "youtube",
            "type": "playlist",
            "title": info.get("title"),
            "total": len(videos),
            "videos": videos,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ======================================================
# UNIVERSAL DOWNLOAD (ALL PLATFORMS)
# ======================================================

@app.get("/download")
def download_video(
    url: str,
    index: int,
    profile: str,
    quality: str = "best"
):
    """
    Downloads ONE video per request.
    Used for:
    - TikTok
    - YouTube (single + playlist queue)
    - Instagram
    - Facebook
    - Likee
    """
    tmp_dir = tempfile.mkdtemp()
    filename = f"{clean_name(profile)}_{index:03d}.mp4"
    filepath = os.path.join(tmp_dir, filename)

    try:
        ydl_opts = {
            "outtmpl": filepath,
            "format": get_format(quality),
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
