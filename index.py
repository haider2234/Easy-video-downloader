from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

# We drop the strict root_path setting and explicitly accept both routes 
# to guarantee a match on Vercel's multi-layered gateway.
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

# By declaring BOTH paths, we guarantee it works locally under /api/analyze 
# AND live on Vercel if it strips the prefix down to /analyze.
@app.post("/analyze")
@app.post("/api/analyze")
async def analyze_video(request: AnalyzeRequest):
    ydl_opts = {
        'skip_download': True, 
        'quiet': True,
        'format': 'best',
        'no_warnings': True
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            formats = info.get('formats', [])
            
            available_formats = []
            seen_resolutions = set()

            for f in formats[::-1]:
                res = f.get('height')
                if res and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
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
                    'resolution': 'Standard Quality',
                    'ext': info.get('ext') or 'mp4',
                    'direct_url': info.get('url')
                })
            
            if not available_formats:
                raise HTTPException(status_code=404, detail="No streaming links could be resolved.")
                
            return {
                "title": info.get('title', 'Extracted Video Asset'),
                "thumbnail": info.get('thumbnail'),
                "formats": available_formats
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
