from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import subprocess

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

# =========================
# PROFILE SCRAPER
# =========================
@app.get("/profile")
def profile(profile_url: str):
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(profile_url, download=False)

    return {
        "total": len(info.get("entries", [])),
        "videos": [
            e["url"] for e in info.get("entries", []) if e.get("url")
        ]
    }

# =========================
# VIDEO DOWNLOAD + FILTERS
# =========================
@app.get("/download")
def download(
    url: str,
    name: str,
    bw: bool = False,
    mirror: bool = False
):
    tmp = tempfile.mkdtemp()
    raw = os.path.join(tmp, "raw.mp4")
    final = os.path.join(tmp, name)

    ydl_opts = {
        "outtmpl": raw,
        "format": "best",
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        filters = []
        if bw:
            filters.append("format=gray")
        if mirror:
            filters.append("hflip")

        if filters:
            subprocess.run([
                "ffmpeg", "-y",
                "-i", raw,
                "-vf", ",".join(filters),
                final
            ], check=True)
        else:
            os.rename(raw, final)

        def stream():
            with open(final, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(final)
                os.rmdir(tmp)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={"Content-Disposition": f'attachment; filename="{name}"'}
        )

    except Exception as e:
        raise HTTPException(400, str(e))
