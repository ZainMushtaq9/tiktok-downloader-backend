from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(title="Universal Video Downloader API", version="2.0")

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
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

def stream_and_cleanup(path: str, tmp_dir: str):
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            yield chunk
    try:
        os.remove(path)
        os.rmdir(tmp_dir)
    except:
        pass

# ======================================================
# HEALTH
# ======================================================
@app.get("/")
def health():
    return {"status": "ok", "service": "downloader-core"}

# ======================================================
# PREVIEW (SINGLE VIDEO)
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    """
    Extract metadata for a single public video.
    Guaranteed title + thumbnail fallback.
    """

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        raise HTTPException(400, "Unable to fetch preview data")

    return {
        "title": info.get("title") or "Public Video",
        "uploader": info.get("uploader") or "Unknown",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "platform": info.get("extractor_key"),
        "webpage_url": info.get("webpage_url")
    }

# ======================================================
# PROFILE (PAGINATED)
# ======================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100)
):
    """
    Extract public videos from profile/page with pagination.
    """

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
            "thumbnail": e.get("thumbnail")
        })

    return {
        "profile": clean_name(info.get("uploader") or info.get("title") or "profile"),
        "total": total,
        "page": page,
        "limit": limit,
        "has_next": end < total,
        "videos": videos
    }

# ======================================================
# DOWNLOAD (SINGLE VIDEO)
# ======================================================
@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
    quality: str = Query("best")
):
    tmp = tempfile.mkdtemp()
    filename = f"{index}.mp4"
    path = os.path.join(tmp, filename)

    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "outtmpl": path,
        "merge_output_format": "mp4",
        "format": quality,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception:
        raise HTTPException(400, "Download failed")

    if not os.path.exists(path):
        raise HTTPException(400, "File not created")

    safe_profile = clean_name(profile)

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_profile}_{index}.mp4"'
        }
    )
