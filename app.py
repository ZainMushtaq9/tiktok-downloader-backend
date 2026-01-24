from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re
from typing import Optional

app = FastAPI(title="Multi Platform Downloader API")

# =========================
# CORS (GitHub Pages SAFE)
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# HELPERS
# =========================

def clean(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

def ydl_base_opts():
    return {
        "quiet": True,
        "nocheckcertificate": True,
        "noplaylist": True,
    }

# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "ok", "service": "downloader-backend"}

# ======================================================
# UNIVERSAL INFO ENDPOINT (VIDEO OR PLAYLIST)
# ======================================================
@app.get("/info")
def extract_info(url: str):
    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid URL")

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
                "url": info.get("webpage_url"),
            }

        # PLAYLIST
        videos = []
        for i, entry in enumerate(info["entries"], start=1):
            if not entry:
                continue

            videos.append({
                "index": i,
                "title": entry.get("title"),
                "url": entry.get("url") or entry.get("webpage_url"),
                "thumbnail": entry.get("thumbnail"),
            })

        return {
            "type": "playlist",
            "title": info.get("title"),
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
# =========================
# INSTAGRAM SINGLE VIDEO DOWNLOAD
# =========================

# ======================================================
# UNIVERSAL DOWNLOAD ENDPOINT
# ======================================================

@app.get("/download")
def download(
    url: str,
    filename: Optional[str] = "video",
    quality: Optional[str] = "best"
):
    tmp_dir = tempfile.mkdtemp()
    safe_name = clean(filename)
    output = os.path.join(tmp_dir, f"{safe_name}.mp4")

    try:
        if quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        elif quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best"
        else:
            fmt = "best"

        opts = ydl_base_opts()
        opts.update({
            "format": fmt,
            "outtmpl": output,
            "merge_output_format": "mp4",
        })

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output):
            raise Exception("Download failed")

        def stream():
            with open(output, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(output)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_name}.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))





# =========================
# INSTAGRAM SINGLE VIDEO DOWNLOAD
# =========================

@app.get("/instagram/download")
def instagram_download(
    url: str,
    quality: str = "best"
):
    tmp_dir = tempfile.mkdtemp()
    filename = "instagram_video.mp4"
    filepath = os.path.join(tmp_dir, filename)

    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid Instagram URL")

        ydl_opts = {
            "outtmpl": filepath,
            "format": quality,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filepath):
            raise Exception("Instagram video download failed")

        def stream():
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(filepath)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": 'attachment; filename="instagram_video.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))





# =========================
# FACEBOOK SINGLE VIDEO DOWNLOAD
# =========================

@app.get("/facebook/download")
def facebook_download(
    url: str,
    quality: str = "best"
):
    tmp_dir = tempfile.mkdtemp()
    filename = "facebook_video.mp4"
    filepath = os.path.join(tmp_dir, filename)

    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid Facebook URL")

        ydl_opts = {
            "outtmpl": filepath,
            "format": quality,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filepath):
            raise Exception("Facebook video download failed")

        def stream():
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(filepath)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": 'attachment; filename="facebook_video.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




# =========================
# LIKEE SINGLE VIDEO DOWNLOAD
# =========================

@app.get("/likee/download")
def likee_download(
    url: str,
    quality: str = "best"
):
    tmp_dir = tempfile.mkdtemp()
    filename = "likee_video.mp4"
    filepath = os.path.join(tmp_dir, filename)

    try:
        if not url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid Likee URL")

        ydl_opts = {
            "outtmpl": filepath,
            "format": quality,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filepath):
            raise Exception("Likee video download failed")

        def stream():
            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(filepath)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={
                "Content-Disposition": 'attachment; filename="likee_video.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))




            

