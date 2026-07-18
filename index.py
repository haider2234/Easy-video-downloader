from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

# We explicitly tell FastAPI to handle routes starting with /api
# This prevents Vercel's proxy from confusing the internal routing path.
app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

# To guarantee a clean match across local development (vercel dev) 
# and the live production edge, we define both absolute paths.
@app.post("/api/analyze")
@app.post("/analyze")
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
