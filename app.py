from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re

app = FastAPI(title="Video Downloader API", version="1.0")

# ======================================================
# CORS (GitHub Pages / Browser Safe)
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

def clean_filename(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\\-]", "_", text)

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
        "merge_output_format": "mp4",
    }

# ======================================================
# HEALTH
# ======================================================

@app.get("/")
def health():
    return {"status": "ok", "service": "downloader-backend"}

# ======================================================
# TIKTOK
# ======================================================

@app.get("/tiktok/profile")
def tiktok_profile(profile_url: str = Query(...)):
    if "tiktok.com" not in profile_url:
        raise HTTPException(400, "Invalid TikTok profile URL")

    opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(profile_url, download=False)

    videos = []
    for i, e in enumerate(info.get("entries", []), start=1):
        if not e or not e.get("url"):
            continue
        videos.append({
            "index": i,
            "url": e["url"],
            "thumbnail": e.get("thumbnail")
        })

    return {
        "type": "profile",
        "platform": "tiktok",
        "total": len(videos),
        "videos": videos
    }

@app.get("/tiktok/single")
def tiktok_single(url: str = Query(...)):
    if "tiktok.com" not in url:
        raise HTTPException(400, "Invalid TikTok video URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "tiktok.mp4")

    opts = base_ydl()
    opts["outtmpl"] = path

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "TikTok download failed")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="tiktok.mp4"'}
    )

# ======================================================
# YOUTUBE
# ======================================================

@app.get("/youtube/info")
def youtube_info(url: str = Query(...)):
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(400, "Invalid YouTube URL")

    opts = {
        "quiet": True,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "nocheckcertificate": True,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if "entries" not in info:
        return {
            "type": "single",
            "platform": "youtube",
            "title": info.get("title"),
            "url": info.get("webpage_url"),
            "thumbnail": info.get("thumbnail")
        }

    videos = []
    for i, e in enumerate(info["entries"], start=1):
        if not e or not e.get("url"):
            continue
        videos.append({
            "index": i,
            "title": e.get("title"),
            "url": e["url"]
        })

    return {
        "type": "playlist",
        "platform": "youtube",
        "title": info.get("title"),
        "total": len(videos),
        "videos": videos
    }

@app.get("/youtube/single")
def youtube_single(url: str = Query(...)):
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(400, "Invalid YouTube video URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "youtube.mp4")

    opts = base_ydl()
    opts.update({
        "format": "best",
        "outtmpl": path,
    })

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "YouTube download failed")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="youtube.mp4"'}
    )

# ======================================================
# INSTAGRAM (SINGLE ONLY)
# ======================================================

@app.get("/instagram/single")
def instagram_single(url: str = Query(...)):
    if "instagram.com" not in url:
        raise HTTPException(400, "Invalid Instagram URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "instagram.mp4")

    opts = base_ydl()
    opts["outtmpl"] = path

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Instagram download failed")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="instagram.mp4"'}
    )

# ======================================================
# FACEBOOK (SINGLE ONLY)
# ======================================================

@app.get("/facebook/single")
def facebook_single(url: str = Query(...)):
    if "facebook.com" not in url:
        raise HTTPException(400, "Invalid Facebook URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "facebook.mp4")

    opts = base_ydl()
    opts["outtmpl"] = path

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Facebook download failed")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="facebook.mp4"'}
    )

# ======================================================
# LIKEE (SINGLE ONLY)
# ======================================================

@app.get("/likee/single")
def likee_single(url: str = Query(...)):
    if "likee" not in url:
        raise HTTPException(400, "Invalid Likee URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "likee.mp4")

    opts = base_ydl()
    opts["outtmpl"] = path

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Likee download failed")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="likee.mp4"'}
    )
