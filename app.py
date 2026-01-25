from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re
import requests

app = FastAPI(title="Universal Video Downloader API", version="3.0")

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
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "video")

def resolve_url(url: str) -> str:
    try:
        r = requests.head(url, allow_redirects=True, timeout=10)
        return r.url
    except:
        return url

def stream_and_cleanup(path: str, tmp_dir: str):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
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
# PREVIEW (SINGLE VIDEO ONLY)
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    resolved = resolve_url(url)

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 10,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(resolved, download=False)
    except Exception as e:
        raise HTTPException(400, f"Preview failed")

    return {
        "title": info.get("title") or "Public TikTok Video",
        "uploader": info.get("uploader") or info.get("uploader_id") or "Public Account",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "platform": info.get("extractor_key"),
        "webpage_url": info.get("webpage_url"),
    }

# ======================================================
# PROFILE (URL LIST ONLY – PAGINATED)
# ======================================================
@app.get("/profile")
def profile(
    profile_url: str = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=60),
):
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
    except:
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
            "url": resolve_url(e["url"]),
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
# DOWNLOAD (ROBUST TIKTOK HANDLING)
# ======================================================
@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
    quality: str = Query("best"),
):
    resolved = resolve_url(url)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, f"{index}.mp4")

    ydl_opts = {
        "quiet": True,
        "format": quality,
        "outtmpl": path,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([resolved])
    except Exception:
        raise HTTPException(400, "Download failed")

    if not os.path.exists(path):
        raise HTTPException(400, "File not created")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{clean_name(profile)}_{index}.mp4"'
        },
    )
