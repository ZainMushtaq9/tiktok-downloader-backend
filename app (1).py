"""
Video Downloader Tools - Multi-Platform Backend API
Supports: TikTok, YouTube, Instagram, Facebook, Twitter, Likee
GitHub: https://github.com/ZainMushtaq9/tiktok-downloader-backend
"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import yt_dlp
import tempfile
import os
import re
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
import validators

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Config:
    RATE_LIMIT_WINDOW = 20
    RATE_LIMIT_MAX_REQUESTS = 15
    SOCKET_TIMEOUT = 15
    MAX_FILE_SIZE = 100
    CHUNK_SIZE = 1024 * 1024
    MAX_PROFILE_VIDEOS = 100
    
    SUPPORTED_PLATFORMS = {
        'tiktok.com': 'TikTok', 'youtube.com': 'YouTube', 'youtu.be': 'YouTube',
        'instagram.com': 'Instagram', 'facebook.com': 'Facebook', 'fb.watch': 'Facebook',
        'twitter.com': 'Twitter', 'x.com': 'Twitter', 'likee.video': 'Likee'
    }

config = Config()

class RateLimiter:
    def __init__(self):
        self.requests: Dict[str, List[datetime]] = defaultdict(list)
        self.last_cleanup = datetime.now()
    
    def _cleanup_old_entries(self):
        now = datetime.now()
        if (now - self.last_cleanup).seconds > 300:
            cutoff = now - timedelta(seconds=config.RATE_LIMIT_WINDOW * 2)
            for ip in list(self.requests.keys()):
                self.requests[ip] = [t for t in self.requests[ip] if t > cutoff]
                if not self.requests[ip]:
                    del self.requests[ip]
            self.last_cleanup = now
    
    def check_rate_limit(self, ip: str) -> None:
        self._cleanup_old_entries()
        now = datetime.now()
        window_start = now - timedelta(seconds=config.RATE_LIMIT_WINDOW)
        self.requests[ip] = [t for t in self.requests[ip] if t > window_start]
        
        if len(self.requests[ip]) >= config.RATE_LIMIT_MAX_REQUESTS:
            raise HTTPException(429, f"Too many requests. Wait {config.RATE_LIMIT_WINDOW}s.")
        
        self.requests[ip].append(now)

rate_limiter = RateLimiter()

def sanitize_filename(text: str, max_length: int = 100) -> str:
    if not text: return "video"
    sanitized = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[-\s]+', '_', sanitized)[:max_length]

def validate_url(url: str) -> tuple[bool, Optional[str]]:
    if not validators.url(url): return False, None
    url_lower = url.lower()
    blocked = ['localhost', '127.0.0.1', '0.0.0.0', '192.168.', '10.0.', '172.16.']
    if any(p in url_lower for p in blocked): return False, None
    for domain, platform in config.SUPPORTED_PLATFORMS.items():
        if domain in url_lower: return True, platform
    return False, None

def stream_file_and_cleanup(file_path: str, temp_dir: str):
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(config.CHUNK_SIZE):
                yield chunk
    finally:
        try:
            if os.path.exists(file_path): os.remove(file_path)
            if os.path.exists(temp_dir): os.rmdir(temp_dir)
        except: pass

def get_ydl_opts(platform: str, download: bool = False, output_path: str = None, extract_flat: bool = False) -> dict:
    opts = {
        'quiet': True, 'no_warnings': True, 'socket_timeout': config.SOCKET_TIMEOUT,
        'nocheckcertificate': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
        'max_filesize': config.MAX_FILE_SIZE * 1024 * 1024,
    }
    
    if extract_flat:
        opts.update({'extract_flat': True, 'skip_download': True})
    elif download:
        opts.update({'format': f'best[filesize<{config.MAX_FILE_SIZE}M]/best', 'merge_output_format': 'mp4', 'outtmpl': output_path})
    else:
        opts['skip_download'] = True
    
    return opts

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Multi-Platform Video Downloader API started")
    logger.info(f"📍 Platforms: {', '.join(set(config.SUPPORTED_PLATFORMS.values()))}")
    yield
    logger.info("👋 API shutting down")

app = FastAPI(title="Multi-Platform Video Downloader", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"]
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Error: {exc}", exc_info=True)
    return JSONResponse(500, {"detail": "An error occurred. Please try again."})

@app.get("/")
async def root():
    return {
        "status": "operational", "service": "Multi-Platform Video Downloader",
        "version": "3.0.0",
        "platforms": ["TikTok", "YouTube", "Instagram", "Facebook", "Twitter", "Likee"],
        "endpoints": ["/preview", "/profile", "/download"],
        "github": "https://github.com/ZainMushtaq9/tiktok-downloader-backend"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "active_ips": len(rate_limiter.requests)}

@app.get("/preview")
async def preview_video(url: str = Query(...), request: Request = None):
    rate_limiter.check_rate_limit(request.client.host)
    is_valid, platform = validate_url(url)
    if not is_valid:
        raise HTTPException(400, "Invalid URL or unsupported platform")
    
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts(platform)) as ydl:
            info = ydl.extract_info(url, download=False)
        
        return {
            "platform": platform, "title": info.get('title', 'Untitled'),
            "uploader": info.get('uploader', 'Unknown'), "duration": info.get('duration'),
            "view_count": info.get('view_count'), "url": url
        }
    except:
        raise HTTPException(422, f"{platform} video unavailable")

@app.get("/profile")
async def fetch_profile(profile_url: str = Query(...), page: int = Query(1, ge=1, le=20), 
                       limit: int = Query(24, ge=1, le=50), request: Request = None):
    rate_limiter.check_rate_limit(request.client.host)
    is_valid, platform = validate_url(profile_url)
    if not is_valid:
        raise HTTPException(400, "Invalid URL")
    
    for _ in range(2):
        try:
            with yt_dlp.YoutubeDL(get_ydl_opts(platform, extract_flat=True)) as ydl:
                info = ydl.extract_info(profile_url, download=False)
            break
        except:
            time.sleep(1)
    else:
        raise HTTPException(422, f"Failed to fetch {platform} profile")
    
    entries = info.get('entries', [])
    total = min(len(entries), config.MAX_PROFILE_VIDEOS)
    start, end = (page - 1) * limit, page * limit
    
    videos = []
    for i, e in enumerate(entries[start:end], start=start + 1):
        url = e.get('url') or e.get('webpage_url')
        if url:
            videos.append({"index": i, "url": url, "title": e.get('title', f'Video {i}'), 
                          "duration": e.get('duration')})
    
    return {"platform": platform, "profile": sanitize_filename(info.get('uploader', 'profile')),
            "total": total, "page": page, "has_next": end < total, "videos": videos}

@app.get("/download")
async def download_video(url: str = Query(...), index: int = Query(1), 
                        profile: str = Query("video"), request: Request = None):
    rate_limiter.check_rate_limit(request.client.host)
    is_valid, platform = validate_url(url)
    if not is_valid:
        raise HTTPException(400, "Invalid URL")
    
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{index}.mp4")
    
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts(platform, download=True, output_path=file_path)) as ydl:
            ydl.download([url])
        
        if not os.path.exists(file_path):
            raise HTTPException(500, "Download failed")
        
        filename = f"{platform.lower()}_{sanitize_filename(profile)}_{index}.mp4"
        return StreamingResponse(stream_file_and_cleanup(file_path, temp_dir), media_type="video/mp4",
                                headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except:
        try:
            if os.path.exists(file_path): os.remove(file_path)
            if os.path.exists(temp_dir): os.rmdir(temp_dir)
        except: pass
        raise HTTPException(422, f"{platform} download failed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
