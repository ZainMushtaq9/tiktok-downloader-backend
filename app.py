from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(
    title="Universal Video Downloader API",
    version="1.1"
)

# ======================================================
# CORS (Browser + GitHub Pages safe)
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
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "video")

def stream_and_cleanup(path: str, tmp_dir: str):
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            yield chunk
    try:
        os.remove(path)
        os.rmdir(tmp_dir)
    except:
        pass

def base_ydl():
    return {
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

# ======================================================
# HEALTH CHECK
# ======================================================

@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "universal-downloader"
    }

# ======================================================
# PREVIEW (SINGLE VIDEO DETAILS)
# ======================================================

@app.get("/preview")
def preview(url: str = Query(...)):
    """
    Fetch metadata for a public video.
    Used for thumbnail + title + duration preview.
    """

    opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        raise HTTPException(400, "Unable to fetch preview information")

    return {
        "title": info.get("title"),
        "uploader": info.get("uploader"),
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail"),
        "webpage_url": info.get("webpage_url"),
        "platform": info.get("extractor_key")
    }

# ======================================================
# PROFILE / PAGE VIDEOS (FLAT LIST)
# ======================================================

@app.get("/profile")
def profile(profile_url: str = Query(...)):
    """
    Extract public video URLs from a profile/page.
    Works for any yt-dlp supported platform.
    """

    opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
    except Exception:
        raise HTTPException(400, "Unable to extract profile data")

    profile_name = clean_name(
        info.get("uploader") or info.get("title") or "profile"
    )

    videos = []
    for i, e in enumerate(info.get("entries", []), start=1):
        if e and e.get("url"):
            videos.append({
                "index": i,
                "url": e["url"],
                "title": e.get("title"),
                "thumbnail": e.get("thumbnail")
            })

    return {
        "profile": profile_name,
        "total": len(videos),
        "videos": videos
    }

# ======================================================
# SINGLE VIDEO DOWNLOAD
# ======================================================

@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
    quality: str = Query("best")
):
    """
    Download a single public video.
    """

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, f"{index}.mp4")

    opts = base_ydl()
    opts.update({
        "outtmpl": path,
        "merge_output_format": "mp4",
        "format": quality
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        raise HTTPException(400, "Download failed")

    if not os.path.exists(path):
        raise HTTPException(400, "File not created")

    filename = f"{clean_name(profile)}_{index}.mp4"

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
        )
