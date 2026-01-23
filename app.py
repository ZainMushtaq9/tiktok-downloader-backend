from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import subprocess

app = FastAPI()

@app.get("/")
def health():
    return {"status": "backend running"}


@app.get("/profile/all")
def scrape_profile(profile_url: str):
    try:
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(profile_url, download=False)

        videos = [
            entry["url"]
            for entry in info.get("entries", [])
            if entry.get("url")
        ]

        return {"total": len(videos), "videos": videos}

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/download")
def download_video(url: str, quality: str = "best"):
    tmp = tempfile.mkdtemp()
    raw = os.path.join(tmp, "raw.mp4")
    final = os.path.join(tmp, "final.mp4")

    try:
        fmt = "best"
        if quality == "720p":
            fmt = "bestvideo[height<=720]+bestaudio/best"
        elif quality == "480p":
            fmt = "bestvideo[height<=480]+bestaudio/best"

        ydl_opts = {
            "outtmpl": raw,
            "format": fmt,
            "merge_output_format": "mp4",
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        if not os.path.exists(raw):
            raise Exception("Download failed")

        # black & white (cheap filter)
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw, "-vf", "format=gray", "-c:a", "copy", final],
            check=True
        )

        def stream():
            with open(final, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
            try:
                os.remove(raw)
                os.remove(final)
                os.rmdir(tmp)
            except:
                pass

        return StreamingResponse(
            stream(),
            media_type="video/mp4",
            headers={"Content-Disposition": "attachment; filename=video.mp4"}
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
