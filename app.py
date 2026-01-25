from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re
from typing import List

app = FastAPI(title="Multi Platform Downloader API")

# ======================================================
# CORS (GitHub Pages SAFE)
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

def clean(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

def stream_file(path: str, tmp_dir: str):
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            yield chunk
    try:
        os.remove(path)
        os.rmdir(tmp_dir)
    except:
        pass

def base_ydl_opts():
    return {
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
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
def tiktok_profile(profile_url: str):
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
        if not e:
            continue
        videos.append({
            "index": i,
            "url": e.get("url"),
            "thumbnail": e.get("thumbnail")
        })

    return {
        "profile": clean(info.get("uploader", "tiktok_profile")),
        "total": len(videos),
        "videos": videos
    }

@app.get("/tiktok/download")
def tiktok_download(url: str):
    if "tiktok.com" not in url:
        raise HTTPException(400, "Invalid TikTok video URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "tiktok.mp4")

    opts = base_ydl_opts()
    opts.update({
        "outtmpl": path,
        "merge_output_format": "mp4",
    })

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "TikTok download failed")

    return StreamingResponse(
        stream_file(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="tiktok.mp4"'}
    )

# ======================================================
# YOUTUBE (NOVELTY FEATURE)
# ======================================================

@app.get("/youtube/info")
def youtube_info(url: str):
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

    # SINGLE VIDEO
    if "entries" not in info:
        return {
            "type": "single",
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "url": info.get("webpage_url")
        }

    # PLAYLIST
    videos = []
    for i, e in enumerate(info["entries"], start=1):
        if not e:
            continue
        videos.append({
            "index": i,
            "title": e.get("title"),
            "url": e.get("url")
        })

    return {
        "type": "playlist",
        "title": info.get("title"),
        "total": len(videos),
        "videos": videos
    }

@app.get("/youtube/download")
def youtube_download(url: str):
    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(400, "Invalid YouTube video URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "youtube.mp4")

    opts = base_ydl_opts()
    opts.update({
        "format": "best",
        "outtmpl": path,
        "merge_output_format": "mp4",
    })

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "YouTube download failed")

    return StreamingResponse(
        stream_file(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="youtube.mp4"'}
    )

# ======================================================
# INSTAGRAM
# ======================================================

@app.get("/instagram/download")
def instagram_download(url: str):
    if "instagram.com" not in url:
        raise HTTPException(400, "Invalid Instagram URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "instagram.mp4")

    opts = base_ydl_opts()
    opts.update({"outtmpl": path})

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Instagram download failed")

    return StreamingResponse(
        stream_file(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="instagram.mp4"'}
    )

# ======================================================
# FACEBOOK
# ======================================================

@app.get("/facebook/download")
def facebook_download(url: str):
    if "facebook.com" not in url:
        raise HTTPException(400, "Invalid Facebook URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "facebook.mp4")

    opts = base_ydl_opts()
    opts.update({"outtmpl": path})

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Facebook download failed")

    return StreamingResponse(
        stream_file(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="facebook.mp4"'}
    )

# ======================================================
# LIKEE
# ======================================================

@app.get("/likee/download")
def likee_download(url: str):
    if "likee.video" not in url:
        raise HTTPException(400, "Invalid Likee URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "likee.mp4")

    opts = base_ydl_opts()
    opts.update({"outtmpl": path})

    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

    if not os.path.exists(path):
        raise HTTPException(400, "Likee download failed")

    return StreamingResponse(
        stream_file(path, tmp),
        media_type="video/mp4",
        headers={"Content-Disposition": 'attachment; filename="likee.mp4"'}
    )
