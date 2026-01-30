"""
Video Downloader Tools - Backend API
Production-ready FastAPI application for multi-platform video processing
Supports: TikTok, YouTube, Instagram, Facebook, Likee

GitHub: https://github.com/ZainMushtaq9/tiktok-downloader-backend
Deployed on: Railway
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

# =====================================================
# LOGGING CONFIGURATION
# =====================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================
# CONFIGURATION
# =====================================================
class Config:
    """Application configuration"""
    RATE_LIMIT_WINDOW = 20  # seconds
    RATE_LIMIT_MAX_REQUESTS = 15
    SOCKET_TIMEOUT = 10
    MAX_FILE_SIZE = 50  # MB
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for streaming
    MAX_PROFILE_VIDEOS = 100  # Safety limit
    
    # Supported platforms
    SUPPORTED_PLATFORMS = {
        'tiktok.com': 'TikTok',
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'instagram.com': 'Instagram',
        'facebook.com': 'Facebook',
        'fb.watch': 'Facebook',
        'likee.video': 'Likee',
    }

config = Config()

# =====================================================
# RATE LIMITING
# =====================================================
class RateLimiter:
    """Enhanced rate limiter with automatic cleanup"""
    
    def __init__(self):
        self.requests: Dict[str, List[datetime]] = defaultdict(list)
        self.last_cleanup = datetime.now()
    
    def _cleanup_old_entries(self):
        """Periodic cleanup of old rate limit data"""
        now = datetime.now()
        if (now - self.last_cleanup).seconds > 300:  # Cleanup every 5 minutes
            cutoff = now - timedelta(seconds=config.RATE_LIMIT_WINDOW * 2)
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    t for t in self.requests[ip] 
                    if t > cutoff
                ]
                if not self.requests[ip]:
                    del self.requests[ip]
            self.last_cleanup = now
            logger.info(f"Rate limiter cleanup completed. Active IPs: {len(self.requests)}")
    
    def check_rate_limit(self, ip: str) -> None:
        """Check if IP has exceeded rate limit"""
        self._cleanup_old_entries()
        
        now = datetime.now()
        window_start = now - timedelta(seconds=config.RATE_LIMIT_WINDOW)
        
        # Filter recent requests
        self.requests[ip] = [
            t for t in self.requests[ip] 
            if t > window_start
        ]
        
        if len(self.requests[ip]) >= config.RATE_LIMIT_MAX_REQUESTS:
            logger.warning(f"Rate limit exceeded for IP: {ip}")
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Please wait {config.RATE_LIMIT_WINDOW} seconds before trying again."
            )
        
        self.requests[ip].append(now)

rate_limiter = RateLimiter()

# =====================================================
# UTILITY FUNCTIONS
# =====================================================
def sanitize_filename(text: str, max_length: int = 100) -> str:
    """Sanitize text for use in filenames"""
    if not text:
        return "video"
    # Remove special characters and limit length
    sanitized = re.sub(r'[^\w\s-]', '', text)
    sanitized = re.sub(r'[-\s]+', '_', sanitized)
    return sanitized[:max_length]

def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """
    Validate URL format and check if platform is supported
    Returns: (is_valid, platform_name)
    """
    # Basic URL validation
    if not validators.url(url):
        return False, None
    
    url_lower = url.lower()
    
    # Security: Prevent SSRF attacks
    blocked_patterns = [
        'localhost', '127.0.0.1', '0.0.0.0', '192.168.',
        '10.0.', '172.16.', '169.254.', '::1', 'file://'
    ]
    if any(pattern in url_lower for pattern in blocked_patterns):
        return False, None
    
    # Check supported platforms
    for domain, platform in config.SUPPORTED_PLATFORMS.items():
        if domain in url_lower:
            return True, platform
    
    return False, None

def stream_file_and_cleanup(file_path: str, temp_dir: str):
    """Stream file content and cleanup temporary files"""
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(config.CHUNK_SIZE):
                yield chunk
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        raise
    finally:
        # Cleanup
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted file: {file_path}")
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
                logger.debug(f"Deleted directory: {temp_dir}")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

def get_ydl_opts(
    download: bool = False,
    output_path: str = None,
    extract_flat: bool = False
) -> dict:
    """Get yt-dlp options with security and performance settings"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'socket_timeout': config.SOCKET_TIMEOUT,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        # Security: Restrict download
        'max_filesize': config.MAX_FILE_SIZE * 1024 * 1024,
    }
    
    if extract_flat:
        opts['extract_flat'] = True
        opts['skip_download'] = True
    elif download:
        opts['format'] = f'best[filesize<{config.MAX_FILE_SIZE}M]/best'
        opts['merge_output_format'] = 'mp4'
        opts['outtmpl'] = output_path
    else:
        opts['skip_download'] = True
    
    return opts

# =====================================================
# LIFESPAN MANAGEMENT
# =====================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("🚀 Video Downloader API starting up...")
    logger.info("📍 Deployed on Railway")
    logger.info("🔗 GitHub: https://github.com/ZainMushtaq9/tiktok-downloader-backend")
    yield
    logger.info("👋 Video Downloader API shutting down...")

# =====================================================
# FASTAPI APPLICATION
# =====================================================
app = FastAPI(
    title="Video Downloader Tools API",
    description="Multi-platform video processing API supporting TikTok, YouTube, Instagram, Facebook, and Likee",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration - Allow your frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # For development
        "https://zainmushtaq9.github.io",  # Your GitHub Pages domain
        "https://tiktok-downloader-ui.vercel.app",  # If using Vercel
        "https://tiktok-downloader-ui.netlify.app",  # If using Netlify
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# =====================================================
# EXCEPTION HANDLERS
# =====================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

# =====================================================
# ENDPOINTS
# =====================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "operational",
        "service": "Video Downloader Tools API",
        "version": "2.0.0",
        "supported_platforms": list(config.SUPPORTED_PLATFORMS.values()),
        "github": "https://github.com/ZainMushtaq9/tiktok-downloader-backend",
        "frontend": "https://github.com/ZainMushtaq9/tiktok-downloader-ui"
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "rate_limiter_active_ips": len(rate_limiter.requests),
        "deployed_on": "Railway"
    }

@app.get("/preview")
async def preview_video(
    url: str = Query(..., description="Video URL to preview"),
    request: Request = None
):
    """
    Preview single video metadata
    Returns: title, uploader, duration, thumbnail (optional)
    """
    # Rate limiting
    rate_limiter.check_rate_limit(request.client.host)
    
    # Validate URL
    is_valid, platform = validate_url(url)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL or unsupported platform. Supported: TikTok, YouTube, Instagram, Facebook, Likee"
        )
    
    logger.info(f"Preview request for {platform}: {url[:50]}...")
    
    try:
        with yt_dlp.YoutubeDL(get_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
        
        if not info:
            raise HTTPException(
                status_code=422,
                detail="Unable to fetch video information. Video may be private or unavailable."
            )
        
        return {
            "platform": platform,
            "title": info.get('title', 'Untitled Video'),
            "uploader": info.get('uploader') or info.get('channel', 'Unknown'),
            "duration": info.get('duration'),
            "view_count": info.get('view_count'),
            "upload_date": info.get('upload_date'),
            "url": url
        }
    
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(
            status_code=422,
            detail="Video unavailable or private. Please check the URL and try again."
        )
    except Exception as e:
        logger.error(f"Preview error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process video. Please try again."
        )

@app.get("/profile")
async def fetch_profile(
    profile_url: str = Query(..., description="Profile/channel/playlist URL"),
    page: int = Query(1, ge=1, le=20, description="Page number"),
    limit: int = Query(24, ge=1, le=50, description="Videos per page"),
    request: Request = None
):
    """
    Fetch public videos from a profile/channel/playlist
    Returns paginated list of videos
    """
    # Rate limiting
    rate_limiter.check_rate_limit(request.client.host)
    
    # Validate URL
    is_valid, platform = validate_url(profile_url)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL or unsupported platform"
        )
    
    logger.info(f"Profile request for {platform}: page {page}, limit {limit}")
    
    # Retry logic
    max_retries = 2
    for attempt in range(max_retries):
        try:
            with yt_dlp.YoutubeDL(get_ydl_opts(extract_flat=True)) as ydl:
                info = ydl.extract_info(profile_url, download=False)
            break
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Profile fetch failed after {max_retries} attempts: {e}")
                raise HTTPException(
                    status_code=422,
                    detail="Failed to fetch profile. Please verify the URL and try again."
                )
            time.sleep(1)
    
    entries = info.get('entries', [])
    if not entries:
        return {
            "platform": platform,
            "profile": sanitize_filename(info.get('uploader') or info.get('title') or 'profile'),
            "total": 0,
            "page": page,
            "has_next": False,
            "videos": []
        }
    
    # Apply safety limit
    total = min(len(entries), config.MAX_PROFILE_VIDEOS)
    entries = entries[:total]
    
    # Pagination
    start = (page - 1) * limit
    end = start + limit
    
    videos = []
    for i, entry in enumerate(entries[start:end], start=start + 1):
        video_url = entry.get('url') or entry.get('webpage_url')
        if video_url:
            videos.append({
                "index": i,
                "url": video_url,
                "title": entry.get('title', f'Video {i}'),
                "duration": entry.get('duration'),
                "view_count": entry.get('view_count')
            })
    
    return {
        "platform": platform,
        "profile": sanitize_filename(info.get('uploader') or info.get('title') or 'profile'),
        "total": total,
        "page": page,
        "limit": limit,
        "has_next": end < total,
        "videos": videos
    }

@app.get("/download")
async def download_video(
    url: str = Query(..., description="Video URL to download"),
    index: int = Query(1, ge=1, description="Video index for filename"),
    profile: str = Query("video", description="Profile name for filename"),
    request: Request = None
):
    """
    Download video and stream response
    Files are temporarily stored and immediately deleted after streaming
    """
    # Rate limiting
    rate_limiter.check_rate_limit(request.client.host)
    
    # Validate URL
    is_valid, platform = validate_url(url)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL or unsupported platform"
        )
    
    logger.info(f"Download request for {platform}: {url[:50]}...")
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp()
    file_path = os.path.join(temp_dir, f"{index}.mp4")
    
    try:
        # Download video
        with yt_dlp.YoutubeDL(get_ydl_opts(download=True, output_path=file_path)) as ydl:
            ydl.download([url])
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=500,
                detail="Download failed. File was not created."
            )
        
        # Get file size for logging
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        logger.info(f"Download successful: {file_size:.2f}MB")
        
        # Generate filename
        safe_profile = sanitize_filename(profile)
        filename = f"{safe_profile}_{index}.mp4"
        
        # Stream response
        return StreamingResponse(
            stream_file_and_cleanup(file_path, temp_dir),
            media_type="video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Platform": platform
            }
        )
    
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp download error: {e}")
        # Cleanup on error
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass
        
        raise HTTPException(
            status_code=422,
            detail="Video download failed. Video may be private, geo-restricted, or too large (50MB limit)."
        )
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        # Cleanup on error
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
        except:
            pass
        
        raise HTTPException(
            status_code=500,
            detail="An error occurred during download. Please try again."
        )

# =====================================================
# STARTUP MESSAGE
# =====================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
