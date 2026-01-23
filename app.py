from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re

app = FastAPI()

# -------------------------
# HELPERS
# -------------------------

def clean_name(text: str):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "tiktok_profile")

# -------------------------
# HEALTH
# -------------------------

@app.get("/")
def health():
    return {"status": "ok"}

# -------------------------
# SCRAPE PROFILE (FIXED)
# -------------------------

@app.get("/profile")
def get_profile(profile_url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "noplaylist": False
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)

        entries = info.get("entries")
        if not entries:
            raise Exception("No videos found (TikTok may be blocking temporarily)")

        profile = clean_name(info.get("uploader"))

        videos = []
        for i, e in enumerate(entries, start=1):
            if e and e.get("webpage_url"):
                videos.append({
                    "index": i,
                    "url": e["webpage_url"],
                    "thumbnail": e.get("thumbnail")
                })

        return {
            "profile": profile,
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# DOWNLOAD VIDEO
# -------------------------

@app.get("/download")
def download_video(
    url: str,
    index: int,
    profile: str,
    quality: str = "best"
):
    tmp = tempfile.mkdtemp()
    filename = f"{profile}_{index:03d}.mp4"
    out = os.path.join(tmp, filename)

    try:
        if quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        elif quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best"
        else:
            fmt = "best"

        ydl_opts = {
            "outtmpl": out,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        def stream():
            with open(out, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(out)
                os.rmdir(tmp)
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
