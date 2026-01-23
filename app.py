from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import re

app = FastAPI()

def clean_name(text: str):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/profile")
def get_profile(profile_url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)

        username = clean_name(info.get("uploader", "tiktok_profile"))

        videos = []
        for i, e in enumerate(info.get("entries", []), start=1):
            if e.get("url"):
                videos.append({
                    "index": i,
                    "url": e["url"],
                    "id": e.get("id"),
                    "thumbnail": e.get("thumbnail")
                })

        return {
            "profile": username,
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

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
