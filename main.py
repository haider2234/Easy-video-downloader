from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import yt_dlp
import httpx
import os
import tempfile

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

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
                raise HTTPException(status_code=404, detail="No downloadable streaming links could be extracted.")
                
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

# 🔄 🛡️ SOLUTION: The IP-Bypass Proxy Streaming Tunnel
@app.get("/api/download")
async def download_proxy(url: str, title: str = "video", ext: str = "mp4"):
    if not url:
        raise HTTPException(status_code=400, detail="Missing source URL path string.")
    
    # Standard header spoofing so YouTube believes the Vercel server is a media player
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }
    
    client = httpx.AsyncClient(timeout=60.0)
    
    async def stream_generator():
        try:
            # We open an asynchronous connection to stream the video chunk by chunk
            async with client.stream("GET", url, headers=headers) as r:
                r.raise_for_status()
                async for chunk in r.aiter_bytes(chunk_size=1024 * 64): # 64KB Blocks
                    yield chunk
        except Exception as e:
            print(f"Proxy streaming failed mid-transit: {str(e)}")
        finally:
            await client.aclose()

    # Clean the title string for file systems
    safe_title = "".join([c for c in title if c.isalpha() or c.isdigit() or c==' ']).rstrip()
    filename = f"{safe_title}.{ext}"

    # Return the file stream back to the browser with headers forcing a local save file window
    return StreamingResponse(
        stream_generator(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )
