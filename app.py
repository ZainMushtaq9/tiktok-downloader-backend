from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(title="TikTok Downloader API", version="3.0")

# ======================================================
# CORS
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
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "tiktok")

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
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
    }

# ======================================================
# HEALTH
# ======================================================
@app.get("/")
def health():
    return {"status": "ok", "service": "tiktok-downloader"}

# ======================================================
# PREVIEW — SINGLE VIDEO (FAST + GUARANTEED)
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    """
    Extract metadata for ONE public TikTok video.
    Guarantees title + thumbnail.
    """

    if "tiktok.com" not in url:
        raise HTTPException(400, "Invalid TikTok URL")

    opts = base_ydl()
    opts.update({
        "skip_download": True,
        "extract_flat": False,
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        raise HTTPException(400, "Unable to fetch video preview")

    return {
        "title": info.get("title") or "Public TikTok Video",
        "uploader": info.get("uploader") or info.get("channel") or "TikTok User",
        "thumbnail": (
            info.get("thumbnail")
            or (info.get("thumbnails") or [{}])[-1].get("url")
        ),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
    }

# ======================================================
# PROFILE — PAGINATED (FAST, SAFE)
# ======================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
):
    """
    List public videos from a TikTok profile with pagination.
    """

    if "tiktok.com" not in profile_url:
        raise HTTPException(400, "Invalid TikTok profile URL")

    opts = base_ydl()
    opts.update({
        "extract_flat": True,
        "skip_download": True,
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
    except Exception:
        raise HTTPException(400, "Unable to extract profile")

    entries = [e for e in info.get("entries", []) if e and e.get("url")]
    total = len(entries)

    start = (page - 1) * limit
    end = start + limit
    sliced = entries[start:end]

    videos = []
    for i, e in enumerate(sliced, start=start + 1):
        videos.append({
            "index": i,
            "url": e["url"],
            "thumbnail": e.get("thumbnail"),
        })

    return {
        "profile": clean_name(info.get("uploader") or info.get("title")),
        "total": total,
        "page": page,
        "limit": limit,
        "has_next": end < total,
        "videos": videos,
    }

# ======================================================
# DOWNLOAD — SINGLE VIDEO (FIXED)
# ======================================================
@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
):
    """
    Download ONE public TikTok video.
    """

    if "tiktok.com" not in url:
        raise HTTPException(400, "Invalid TikTok URL")

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, f"{index}.mp4")

    opts = base_ydl()
    opts.update({
        "outtmpl": path,
        "noplaylist": True,
        "merge_output_format": "mp4",
        "format": "mp4",
    })

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception:
        raise HTTPException(400, "Download failed")

    if not os.path.exists(path):
        raise HTTPException(400, "File not created")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{clean_name(profile)}_{index}.mp4"'
            )
        },
    )ean_name(profile)}_{index}.mp4"'
        },
    )
