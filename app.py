from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import tempfile
import os

app = FastAPI()

class ResolveRequest(BaseModel):
    url: str

@app.get("/")
def root():
    return {"status": "backend running"}

@app.post("/resolve")
def resolve_and_download(data: ResolveRequest):
    try:
        temp_dir = tempfile.mkdtemp()

        ydl_opts = {
            "outtmpl": os.path.join(temp_dir, "%(id)s.%(ext)s"),
            "format": "mp4",
            "noplaylist": True,
            "quiet": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(data.url, download=True)

        filename = ydl.prepare_filename(info)

        if not os.path.exists(filename):
            raise Exception("Video file not found after download")

        def file_iterator():
            with open(filename, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(filename)
                os.rmdir(temp_dir)
            except Exception:
                pass

        headers = {
            "Content-Disposition": f'attachment; filename="{os.path.basename(filename)}"'
        }

        return StreamingResponse(
            file_iterator(),
            media_type="video/mp4",
            headers=headers
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
