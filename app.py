from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp, tempfile, os, re, time

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
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "")

def stream_and_cleanup(path, tmp):
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            yield chunk
    try:
        os.remove(path)
        os.rmdir(tmp)
    except:
        pass

# ======================================================
# HEALTH
# ======================================================
@app.get("/")
def health():
    return {"status": "ok", "version": "phase-3"}

# ======================================================
# SINGLE VIDEO PREVIEW (FAST FAIL)
# ======================================================
@app.get("/preview")
def preview(url: str = Query(...)):
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "socket_timeout": 8,
        "nocheckcertificate": True,
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VIDEO_BLOCKED",
                "message": "This video cannot be previewed. It may be restricted or removed."
            }
        )

    return {
        "title": info.get("title") or "Public TikTok Video",
        "uploader": info.get("uploader") or "Unknown",
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "webpage_url": info.get("webpage_url"),
    }

# ======================================================
# PROFILE (CLEAR BLOCK DETECTION)
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
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PROFILE_BLOCKED",
                "message": "This TikTok profile restricts automated access."
            }
        )

    entries = [e for e in info.get("entries", []) if e and e.get("url")]

    if not entries:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PROFILE_EMPTY",
                "message": "No publicly accessible videos were found."
            }
        )

    total = len(entries)
    start = (page - 1) * limit
    end = start + limit

    videos = []
    for i, e in enumerate(entries[start:end], start=start + 1):
        videos.append({
            "index": i,
            "url": e["url"],
            "thumbnail": e.get("thumbnail")
        })

    return {
        "profile": clean_name(info.get("uploader") or info.get("title")),
        "total": total,
        "page": page,
        "has_next": end < total,
        "videos": videos
    }

# ======================================================
# DOWNLOAD (STRICT URL CHECK)
# ======================================================
@app.get("/download")
def download(
    url: str,
    index: int,
    profile: str,
):
    if "/video/" not in url and "vt.tiktok.com" not in url:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_DOWNLOAD_URL",
                "message": "Only direct TikTok video URLs can be downloaded."
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
        "http_headers": {"User-Agent": "Mozilla/5.0"},
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "DOWNLOAD_FAILED",
                "message": "TikTok blocked the download request."
            }
        )

    if not os.path.exists(path):
        raise HTTPException(500, "File not created")

    return StreamingResponse(
        stream_and_cleanup(path, tmp),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{clean_name(profile)}_{index}.mp4"'
        }
        )
