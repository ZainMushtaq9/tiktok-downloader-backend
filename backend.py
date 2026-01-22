from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
import tempfile
import os

app = FastAPI()

class ResolveRequest(BaseModel):
    url: str

@app.post("/resolve")
def resolve_video(data: ResolveRequest):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                "outtmpl": f"{tmpdir}/video.%(ext)s",
                "format": "mp4",
                "quiet": True,
                "noplaylist": True
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(data.url, download=True)
                filename = ydl.prepare_filename(info)

            if not os.path.exists(filename):
                raise Exception("Video file not created")

            with open(filename, "rb") as f:
                file_bytes = f.read()

            return {
                "filename": os.path.basename(filename),
                "file_bytes": list(file_bytes)
            }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
