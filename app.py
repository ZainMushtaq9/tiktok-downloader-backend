from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI(title="Universal Video Downloader API", version="1.0")

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
# HEALTH CHECK
# ======================================================

@app.get("/")
def health():
    return {"status": "ok", "service": "downloader-core"}

# ======================================================
# GENERIC PROFILE EXTRACTOR
# ======================================================

@app.get("/profile")
def profile(profile_url: str = Query(...)):
    """
    Extract publicly available video URLs from a profile/page.
    Works for platforms supported by yt-dlp.
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
        raise HTTPException(400, "Unable to extract profile information")

    profile_name = clean_name(info.get("uploader") or info.get("title") or "profile")

    videos = []
    for e in info.get("entries", []):
        if e and e.get("url"):
            videos.append(e["url"])

    return {
        "profile": profile_name,
        "total": len(videos),
        "videos": videos
    }

# ======================================================
# GENERIC VIDEO DOWNLOAD
# ======================================================

@app.get("/download")
def download(
    url: str = Query(...),
    index: int = Query(...),
    profile: str = Query(...),
    quality: str = Query("best")
):
    """
    Download a single public video URL.
    """

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
