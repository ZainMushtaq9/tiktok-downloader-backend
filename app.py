from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(
    title="TikTok Video Downloader API",
    version="3.2-stable"
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


def extract_video_meta(url: str):
    """
    Extract title + thumbnail for ONE TikTok video
    Used by /preview and /profile internally
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
        return {
            "title": None,
            "thumbnail": None,
            "uploader": None,
            "duration": None,
        }

# ======================================================
# HEALTH
# ======================================================
@app.get("/")
def health():
    return {
        "status": "ok",
        "platform": "tiktok",
        "version": "3.2-stable"
    }

# ======================================================
# SINGLE VIDEO PREVIEW
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    meta = extract_video_meta(url)

    if not meta["title"] and not meta["thumbnail"]:
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
# PROFILE SCRAPE (WITH PREVIEW DATA)
# ======================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=50),
):
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
            status_code=422,
            detail={
                "code": "PROFILE_BLOCKED",
                "message": "This TikTok profile does not allow public access."
            }
        )

    entries = [e for e in info.get("entries", []) if e and e.get("url")]

    if not entries:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PROFILE_EMPTY",
                "message": "No public videos found on this profile."
            }
        )

    total = len(entries)
    start = (page - 1) * limit
    end = start + limit

    videos = []

    for i, e in enumerate(entries[start:end], start=start + 1):
        meta = extract_video_meta(e["url"])

        videos.append({
            "index": i,
            "url": e["url"],
            "title": meta["title"] or "Public TikTok Video",
            "thumbnail": meta["thumbnail"],
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
