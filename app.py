from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import tempfile
import os
import re

app = FastAPI()

# =========================
# CORS (REQUIRED for GitHub Pages)
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

def clean_name(text: str):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "ok"}

# =========================
# SCRAPE PROFILE
# =========================

@app.get("/profile")
def get_profile(profile_url: str):
    try:
        if not profile_url.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid profile URL")

        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "forcejson": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)

        username = clean_name(
            info.get("uploader")
            or info.get("channel")
            or "tiktok_profile"
        )

        videos = []
        for i, e in enumerate(info.get("entries", []), start=1):
            if not e:
                continue

            vid = e.get("id") or e.get("url")
            if not vid:
                continue

            url = (
                vid if vid.startswith("http")
                else f"https://www.tiktok.com/@{username}/video/{vid}"
            )

            videos.append({
                "index": i,
                "url": url,
                "thumbnail": e.get("thumbnail")
            })

        return {
            "profile": username,
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# =========================
# DOWNLOAD SINGLE VIDEO
# =========================

@app.get("/download")
def download_video(
    url: str,
    index: int,
    profile: str,
    quality: str = "best"
):
    tmp_dir = tempfile.mkdtemp()
    filename = f"{profile}_{index:03d}.mp4"
    filepath = os.path.join(tmp_dir, filename)

    try:
        if quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        elif quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best"
        else:
            fmt = "best"

        ydl_opts = {
            "outtmpl": filepath,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True,
            "nocheckcertificate": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(filepath):
            raise Exception("Download failed")

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
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
