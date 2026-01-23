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

def clean_name(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text or "tiktok_profile")

def select_format(quality: str) -> str:
    if quality == "720p":
        return "bestvideo[height<=720]+bestaudio/best"
    if quality == "480p":
        return "bestvideo[height<=480]+bestaudio/best"
    return "best"

# -------------------------
# HEALTH
# -------------------------

@app.get("/")
def health():
    return {"status": "backend running"}

# -------------------------
# PROFILE SCRAPER
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
            raise Exception("No videos found (TikTok may be rate limiting)")

        profile = clean_name(info.get("uploader"))

        videos = []
        index = 1
        for e in entries:
            if e and e.get("webpage_url"):
                videos.append({
                    "index": index,
                    "url": e["webpage_url"],
                    "thumbnail": e.get("thumbnail")
                })
                index += 1

        return {
            "profile": profile,
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# DOWNLOAD (STREAM)
# -------------------------

@app.get("/download")
def download_video(
    url: str,
    index: int,
    profile: str,
    quality: str = "best"
):
    tmp_dir = tempfile.mkdtemp()
    filename = f"{clean_name(profile)}_{index:03d}.mp4"
    output_path = os.path.join(tmp_dir, filename)

    try:
        ydl_opts = {
            "outtmpl": output_path,
            "format": select_format(quality),
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(output_path):
            raise Exception("Download failed")

        def stream():
            with open(output_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(output_path)
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
