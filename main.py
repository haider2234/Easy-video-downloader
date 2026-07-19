from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
import httpx
import os
import tempfile

app = FastAPI()

# Enable CORS so your Vercel frontend can communicate securely with this Render backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

def remove_file(path: str):
    """Background task to securely wipe the cached file after transmission completes."""
    if os.path.exists(path):
        try:
            os.remove(path)
            print(f"Successfully cleaned up temporary asset: {path}")
        except Exception as e:
            print(f"Cleanup warning: {str(e)}")

@app.post("/api/analyze")
async def analyze_video(request: AnalyzeRequest):
    ydl_opts = {
        'skip_download': True, 
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'android'],
                'skip': ['dash', 'hls']
            }
        }
    }

    cookies_content = os.getenv("YT_COOKIES")
    temp_cookie_file = None

    if cookies_content:
        try:
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write(cookies_content)
                temp_cookie_file = f.name
            ydl_opts['cookiefile'] = temp_cookie_file
        except Exception as ce:
            print(f"Cookie setup warning: {str(ce)}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            formats = info.get('formats', [])
            available_formats = []
            seen_resolutions = set()

            for f in formats[::-1]:
                res = f.get('height')
                if res and f.get('url'):
                    res_str = f"{res}p"
                    if res_str not in seen_resolutions:
                        seen_resolutions.add(res_str)
                        available_formats.append({
                            'resolution': res_str,
                            'ext': f.get('ext') or 'mp4',
                            'direct_url': f.get('url')
                        })
            
            if not available_formats and info.get('url'):
                available_formats.append({
                    'resolution': 'Default Quality',
                    'ext': info.get('ext') or 'mp4',
                    'direct_url': info.get('url')
                })
            
            if not available_formats:
                raise HTTPException(status_code=404, detail="No downloadable link tracks extracted.")
                
            return {
                "title": info.get('title', 'Extracted Video Asset'),
                "thumbnail": info.get('thumbnail'),
                "formats": available_formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_cookie_file and os.path.exists(temp_cookie_file):
            try:
                os.remove(temp_cookie_file)
            except Exception:
                pass

@app.get("/api/download")
async def download_proxy(
    url: str, 
    title: str = "video", 
    ext: str = "mp4", 
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if not url:
        raise HTTPException(status_code=400, detail="Missing source link parameter.")
    
    # 1. Base browser headers to match an authentic device request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.tiktok.com/",
        "Origin": "https://www.tiktok.com",
        "Connection": "keep-alive"
    }

    # 2. Extract cookies from environment variables to authenticate the file download
    cookies_content = os.getenv("YT_COOKIES")
    cookie_dict = {}
    
    if cookies_content:
        try:
            for line in cookies_content.splitlines():
                if line.strip() and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        # Extract the cookie name and its value string safely
                        cookie_dict[parts[5]] = parts[6]
        except Exception as ce:
            print(f"Failed parsing cookies for download tunnel: {str(ce)}")

    # Generate a unique temp file path in Render's storage directory
    temp_dir = tempfile.gettempdir()
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    if not safe_title:
        safe_title = "download"
    
    local_filename = f"dl_{os.urandom(4).hex()}_{safe_title}.{ext}"
    local_filepath = os.path.join(temp_dir, local_filename)

    try:
        # Download the file directly onto the Render container file system block
        with open(local_filepath, "wb") as f:
            # 🚀 Passing both browser spoofing headers AND authentication cookies
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True, cookies=cookie_dict) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 64):
                        f.write(chunk)
                        
    except Exception as e:
        if os.path.exists(local_filepath):
            try:
                os.remove(local_filepath)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Proxy processing error: {str(e)}")

    # Register the cleanup routine to run immediately after the response finishes streaming
    background_tasks.add_task(remove_file, local_filepath)

    # Return a structural FileResponse, forcing the browser to process it as a single static download
    return FileResponse(
        path=local_filepath,
        media_type="application/octet-stream",
        filename=f"{safe_title}.{ext}"
    )
