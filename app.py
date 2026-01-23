from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import subprocess
import os
import json

app = FastAPI()

# =========================
# MODELS
# =========================

class ProfileRequest(BaseModel):
    profile_url: str


# =========================
# HEALTH
# =========================

@app.get("/")
def health():
    return {"status": "backend running"}


# =========================
# PROFILE STREAM (unchanged)
# =========================

@app.post("/profile/stream")
def stream_profile(data: ProfileRequest):

    def generator():
        ydl_opts = {
            "quiet": True,
            "extract_flat": True,
            "skip_download": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.profile_url, download=False)
            entries = info.get("entries", [])
            total = len(entries)

            for i, e in enumerate(entries, start=1):
                if not e.get("url"):
                    continue

                yield json.dumps({
                    "current": i,
                    "total": total,
                    "url": e["url"]
                }) + "\n"

    return StreamingResponse(generator(), media_type="text/plain")


# =========================
# FILTER MAP
# =========================

FILTERS = {
    "none": None,
    "bw": "format=gray",
    "mirror": "hflip",
    "bw_mirror": "format=gray,hflip",
    "noir": "eq=contrast=1.3:brightness=-0.05:saturation=0.3"
}


# =========================
# DOWNLOAD WITH FILTER
# =========================

@app.get("/download")
def download_video(
    url: str = Query(...),
    n: int = Query(...),
    filter: str = Query("none")
):
    try:
        if filter not in FILTERS:
            raise HTTPException(400, "Invalid filter")

        tmp = tempfile.mkdtemp()
        raw = os.path.join(tmp, "raw.mp4")
        final = os.path.join(tmp, f"{n}.mp4")

        # ---- yt-dlp download ----
        ydl_opts = {
            "outtmpl": raw,
            "format": "best",
            "merge_output_format": "mp4",
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        # ---- FFmpeg filter ----
        if FILTERS[filter]:
            cmd = [
                "ffmpeg", "-y",
                "-i", raw,
                "-vf", FILTERS[filter],
                "-movflags", "faststart",
                final
            ]
        else:
            os.rename(raw, final)
            cmd = None

        if cmd:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if not os.path.exists(final):
            raise Exception("Processing failed")

        # ---- Stream to browser ----
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
            headers={
                "Content-Disposition": f'attachment; filename="{n}.mp4"'
            }
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
