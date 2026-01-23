from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import time
import zipfile
import re
from typing import List

app = FastAPI()

def clean(text: str):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/profile")
def profile(profile_url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)

        username = clean(info.get("uploader", "tiktok_profile"))

        videos = []
        for i, e in enumerate(info.get("entries", []), start=1):
            if e.get("url"):
                videos.append(e["url"])

        return {
            "profile": username,
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/download-all")
def download_all(
    profile: str,
    urls: List[str],
    quality: str = "best",
    sleep_seconds: int = 3
):
    tmp = tempfile.mkdtemp()
    zip_path = os.path.join(tmp, f"{profile}.zip")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, url in enumerate(urls, start=1):
                out = os.path.join(tmp, f"{idx}.mp4")

                ydl_opts = {
                    "outtmpl": out,
                    "format": quality,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "noplaylist": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                if os.path.exists(out):
                    zf.write(out, arcname=f"{idx}.mp4")
                    os.remove(out)

                time.sleep(sleep_seconds)  # ✅ anti-block

        def stream():
            with open(zip_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(zip_path)
                os.rmdir(tmp)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{profile}.zip"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
