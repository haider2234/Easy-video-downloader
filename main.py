from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
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
    # 🛠️ We remove 'format': 'best' so it grabs the entire manifest of streams
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

            # Iterate backwards to process higher qualities first
            for f in formats[::-1]:
                res = f.get('height')
                # Grab video streams. (Note: Premium video-only streams require front-end muxing, 
                # so we pull direct streams that contain active URLs)
                if res and f.get('url'):
                    res_str = f"{res}p"
                    if res_str not in seen_resolutions:
                        seen_resolutions.add(res_str)
                        available_formats.append({
                            'resolution': res_str,
                            'ext': f.get('ext') or 'mp4',
                            'direct_url': f.get('url')
                        })
            
            # Fallback if no specific heights are grouped
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
