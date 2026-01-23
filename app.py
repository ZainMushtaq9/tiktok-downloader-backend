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

# -------------------------
# Helpers
# -------------------------

def clean_name(text: str):
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)

# -------------------------
# Health
# -------------------------

@app.get("/")
def health():
    return {"status": "ok"}

# -------------------------
# Fetch profile (NO delay here)
# -------------------------

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

        profile = clean_name(info.get("uploader", "tiktok_profile"))

        videos = []
        for i, e in enumerate(info.get("entries", []), start=1):
            if e.get("url"):
                videos.append(e["url"])

        return {
            "profile": profile,
            "total": len(videos),
            "videos": videos
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# -------------------------
# Download ALL videos (delay applied HERE only)
# -------------------------

@app.post("/download-all")
def download_all_videos(
    profile: str,
    urls: List[str],
    quality: str = "best",
    sleep_seconds: int = 3   # ✅ delay ONLY for download
):
    tmp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(tmp_dir, f"{profile}.zip")

    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for idx, url in enumerate(urls, start=1):
                out_file = os.path.join(tmp_dir, f"{idx}.mp4")

                ydl_opts = {
                    "outtmpl": out_file,
                    "format": quality,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "noplaylist": True
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                if os.path.exists(out_file):
                    zipf.write(out_file, arcname=f"{idx}.mp4")
                    os.remove(out_file)

                # ✅ Delay AFTER each download
                time.sleep(sleep_seconds)

        def stream_zip():
            with open(zip_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(zip_path)
                os.rmdir(tmp_dir)
            except:
                pass

        return StreamingResponse(
            stream_zip(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{profile}.zip"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
