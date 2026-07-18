from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

@app.post("/api/analyze")
async def analyze_video(request: AnalyzeRequest):
    # 'format': 'best' forces yt-dlp to look for combined video+audio pre-stitched streams
    ydl_opts = {
        'skip_download': True, 
        'quiet': True,
        'format': 'best'
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            formats = info.get('formats', [])
            
            available_formats = []
            seen_resolutions = set()

            # Filter for formats that contain BOTH video and audio layers natively
            for f in formats[::-1]:
                res = f.get('height')
                # Check if it has both video and audio tracks pre-merged by the platform
                if res and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    res_str = f"{res}p"
                    if res_str not in seen_resolutions:
                        seen_resolutions.add(res_str)
                        available_formats.append({
                            'resolution': res_str,
                            'ext': f.get('ext') or 'mp4',
                            'direct_url': f.get('url') # The direct streaming asset URL hosted by the platform
                        })
            
            # Fallback if no mixed formats were detected
            if not available_formats and info.get('url'):
                available_formats.append({
                    'resolution': 'Default Quality',
                    'ext': info.get('ext') or 'mp4',
                    'direct_url': info.get('url')
                })
            
            return {
                "title": info.get('title', 'Video Asset'),
                "thumbnail": info.get('thumbnail'),
                "formats": available_formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))