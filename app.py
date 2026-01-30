from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re
import time

app = FastAPI(
    title="TikTok Downloader API",
    version="7.0-production"
)

# =====================================================
# CORS
# =====================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# BASIC RATE LIMIT
# =====================================================
RATE = {}

def rate_limit(ip: str):
    now = time.time()
    window = RATE.get(ip, [])
    window = [t for t in window if now - t < 20]

    if len(window) > 15:
        raise HTTPException(429, "Too many requests. Slow down.")

    window.append(now)
    RATE[ip] = window

# =====================================================
# HELPERS
# =====================================================
def clean_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "video")

def valid_tiktok(url: str):
    if "tiktok.com" not in url:
        raise HTTPException(400, "Only TikTok URLs allowed")

def stream_and_cleanup(path: str, tmp: str):
    try:
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk
    finally:
        try:
            os.remove(path)
            os.rmdir(tmp)
        except:
            pass

# =====================================================
# SINGLE VIDEO META
# =====================================================
def extract_meta(url: str):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 7,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "title": info.get("title"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
        }

    except:
        return None

# =====================================================
# HEALTH
# =====================================================
@app.get("/")
def health():
    return {
        "status": "ok",
        "mode": "production"
    }

# =====================================================
# PREVIEW (SINGLE VIDEO)
# =====================================================
@app.get("/preview")
def preview(url: str = Query(...), request: Request = None):
    rate_limit(request.client.host)
    valid_tiktok(url)

    meta = extract_meta(url)
    if not meta:
        raise HTTPException(422, "Video unavailable")

    return {
        "title": meta["title"] or "Public TikTok Video",
        "uploader": meta["uploader"] or "Unknown",
        "duration": meta["duration"],
        "url": url
    }

# =====================================================
# PROFILE SCRAPE (LIGHTWEIGHT)
# =====================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=50),
    request: Request = None
):
    rate_limit(request.client.host)
    valid_tiktok(profile_url)

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,   # IMPORTANT
        "skip_download": True,
        "socket_timeout": 8,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    # retry once
    for _ in range(2):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(profile_url, download=False)
            break
        except:
            time.sleep(1)
    else:
        raise HTTPException(422, "Profile fetch failed")

    entries = info.get("entries") or []
    total = len(entries)

    start = (page - 1) * limit
    end = start + limit

    videos = []
    for i, e in enumerate(entries[start:end], start=start + 1):
        if e.get("url"):
            title = e.get("title") or f"Video {i}"

            videos.append({
                "index": i,
                "url": e["url"],
                "title": title
            })

    return {
        "profile": clean_name(info.get("uploader") or info.get("title") or "tiktok_profile"),
        "total": total,
        "page": page,
        "has_next": end < total,
        "videos": videos
    }

# =====================================================
# DOWNLOAD
# =====================================================
@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
    request: Request = None
):
    rate_limit(request.client.host)
    valid_tiktok(url)

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, f"{index}.mp4")

    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "outtmpl": path,
        "merge_output_format": "mp4",
        "format": "mp4[filesize<50M]/best",
        "socket_timeout": 12,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except:
        raise HTTPException(422, "Download blocked")

    if not os.path.exists(path):
        raise HTTPException(500, "File not created")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition":
            f'attachment; filename="{clean_name(profile)}_{index}.mp4"'
        }
            )
