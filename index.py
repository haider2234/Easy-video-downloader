from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

# root_path handles Vercel's implicit prefix routing layout out-of-the-box
app = FastAPI(root_path="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str

@app.post("/analyze")
async def analyze_video(request: AnalyzeRequest):
    # 'format': 'best' targets pre-merged single-stream assets
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

            # Scan the structural metadata payload backwards for top configurations
            for f in formats[::-1]:
                res = f.get('height')
                # Ensure the stream track includes native audio and video configurations
                if res and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    res_str = f"{res}p"
                    if res_str not in seen_resolutions:
                        seen_resolutions.add(res_str)
                        available_formats.append({
                            'resolution': res_str,
                            'ext': f.get('ext') or 'mp4',
                            'direct_url': f.get('url')
                        })
            
            # Universal structural asset fallback router
            if not available_formats and info.get('url'):
                available_formats.append({
                    'resolution': 'Standard Quality',
                    'ext': info.get('ext') or 'mp4',
                    'direct_url': info.get('url')
                })
            
            if not available_formats:
                raise HTTPException(status_code=404, detail="No streaming links could be resolved for this URL.")
                
            return {
                "title": info.get('title', 'Extracted Video Asset'),
                "thumbnail": info.get('thumbnail'),
                "formats": available_formats
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))