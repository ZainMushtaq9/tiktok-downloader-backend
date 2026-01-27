0lfrom fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re

app = FastAPI(
    title="TikTok Downloader API",
    version="4.0-clean"
)

# ======================================================
# CORS (Frontend safe)
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


def stream_and_cleanup(path: str, tmp: str):
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            yield chunk
    try:
        os.remove(path)
        os.rmdir(tmp)
    except:
        pass


def extract_video_meta(url: str):
    """
    Extract title, thumbnail, uploader, duration
    Used by both single preview and profile items
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 8,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
        }

    except:
        return None

# ======================================================
# HEALTH
# ======================================================
@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "tiktok-downloader",
        "mode": "single-request-only"
    }

# ======================================================
# SINGLE VIDEO PREVIEW
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    meta = extract_video_meta(url)

    if not meta:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VIDEO_UNAVAILABLE",
                "message": "Video is private, restricted, or removed."
            }
        )

    return {
        "url": url,
        "title": meta["title"] or "Public TikTok Video",
        "uploader": meta["uploader"] or "Unknown",
        "thumbnail": meta["thumbnail"],
        "duration": meta["duration"],
    }

# ======================================================
# PROFILE SCRAPE (PAGINATED, SAFE)
# ======================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=50),
):
    """
    Returns ONLY metadata.
    No downloads. No auto loops.
    Pagination safe for thousands of videos.
    """
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "socket_timeout": 10,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
    except:
        raise HTTPException(
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(
    title="TikTok Video Downloader API",
    version="4.0-stable"
)

# ======================================================
# CORS (Frontend Safe)
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


def stream_and_cleanup(path: str, tmp: str):
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            yield chunk
    try:
        os.remove(path)
        os.rmdir(tmp)
    except:
        pass


def extract_single_video_meta(url: str):
    """
    SAFE: Single video metadata only
    """
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 8,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "uploader": info.get("uploader"),
            "duration": info.get("duration"),
        }

    except:
        return None


# ======================================================
# HEALTH
# ======================================================
@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "tiktok-downloader",
        "mode": "stable"
    }


# ======================================================
# SINGLE VIDEO PREVIEW
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    meta = extract_single_video_meta(url)

    if not meta:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VIDEO_UNAVAILABLE",
                "message": "This TikTok video is private, restricted, or removed."
            }
        )

    return {
        "title": meta["title"] or "Public TikTok Video",
        "uploader": meta["uploader"] or "Unknown",
        "thumbnail": meta["thumbnail"],
        "duration": meta["duration"],
        "url": url,
    }


# ======================================================
# PROFILE SCRAPE (LIGHTWEIGHT & SAFE)
# ======================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=50),
):
    """
    IMPORTANT:
    - Profile endpoint NEVER extracts video metadata
    - Only returns video URLs + index
    - This prevents TikTok blocking
    """

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "forcejson": True,
        "socket_timeout": 10,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
    except:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PROFILE_FETCH_FAILED",
                "message": "TikTok temporarily blocked profile listing. Try again later."
            }
        )

    entries = info.get("entries") or []

    if not entries:
        return {
            "profile": clean_name(info.get("uploader") or info.get("title") or "tiktok_profile"),
            "total": 0,
            "page": page,
            "has_next": False,
            "videos": []
        }

    total = len(entries)
    start = (page - 1) * limit
    end = start + limit

    videos = []
    for i, e in enumerate(entries[start:end], start=start + 1):
        if e.get("url"):
            videos.append({
                "index": i,
                "url": e["url"]
            })

    return {
        "profile": clean_name(info.get("uploader") or info.get("title") or "tiktok_profile"),
        "total": total,
        "page": page,
        "has_next": end < total,
        "videos": videos
    }


# ======================================================
# DOWNLOAD (DIRECT VIDEO ONLY)
# ======================================================
@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
):
    if "/video/" not in url and "vt.tiktok.com" not in url:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_URL",
                "message": "Only direct TikTok video URLs are supported."
            }
        )

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, f"{index}.mp4")

    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "outtmpl": path,
        "merge_output_format": "mp4",
        "socket_timeout": 15,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "DOWNLOAD_FAILED",
                "message": "TikTok blocked this download request."
            }
        )

    if not os.path.exists(path):
        raise HTTPException(
            status_code=500,
            detail="Download failed. File was not created."
        )

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition":
                f'attachment; filename="{clean_name(profile)}_{index}.mp4"'
        }
    )
