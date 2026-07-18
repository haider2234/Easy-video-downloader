from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import yt_dlp
import os
import uuid
import subprocess

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = "completed_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

class AnalyzeRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format_id: str
    ext: str

@app.get("/", response_class=HTMLResponse)
async def serve_website():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EasyDownloader - Premium HD Video Downloader</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', sans-serif; background-color: #0b1329; }
            .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.08); }
        </style>
    </head>
    <body class="text-slate-100 min-h-screen flex flex-col justify-between selection:bg-blue-500 selection:text-white">

        <!-- HEADER BRAND BAR -->
        <header class="w-full max-w-7xl mx-auto px-6 py-4 flex items-center justify-between border-b border-slate-800">
            <div class="flex items-center gap-3">
                <!-- Premium SVG Logo Element -->
                <div class="p-2 bg-gradient-to-tr from-blue-600 to-indigo-500 rounded-xl shadow-lg shadow-blue-500/20">
                    <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path>
                    </svg>
                </div>
                <span class="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                    Easy<span class="text-blue-500">Downloader</span>
                </span>
            </div>
            <div class="flex items-center gap-2 text-xs font-semibold text-slate-400 bg-slate-800/50 px-3 py-1.5 rounded-full border border-slate-700/50">
                <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span> v2.0 Live
            </div>
        </header>

        <!-- MAIN LAYOUT WITH AD SLOTS -->
        <main class="w-full max-w-7xl mx-auto px-4 py-6 flex flex-col gap-6 items-center flex-1">
            
            <!-- AD SLOT: TOP BANNER (728x90 style) -->
            <div class="w-full max-w-4xl bg-slate-800/30 border border-dashed border-slate-700/60 rounded-xl p-2 text-center text-xs text-slate-500 tracking-wider font-medium min-h-[90px] flex items-center justify-center">
                <!-- Replace this inner div with your real Ad Script code -->
                <div class="ad-placeholder">
                    <p class="uppercase text-[10px] text-blue-500/60 font-bold mb-1">Advertisement</p>
                    <p>Responsive Banner Ad Slot</p>
                </div>
            </div>

            <div class="w-full max-w-7xl grid grid-cols-1 lg:grid-cols-4 gap-6 items-start mt-2">
                
                <!-- SIDEBAR AD SLOT (Left Side on Desktop) -->
                <div class="hidden lg:flex flex-col gap-4 bg-slate-800/30 border border-dashed border-slate-700/60 rounded-2xl p-4 text-center text-xs text-slate-500 min-h-[500px] items-center justify-center">
                    <div class="ad-placeholder">
                        <p class="uppercase text-[10px] text-blue-500/60 font-bold mb-1">Advertisement</p>
                        <p>Sticky Sidebar Banner Space</p>
                        <p class="text-[11px] text-slate-600 mt-2">300 x 250 / 160 x 600</p>
                    </div>
                </div>

                <!-- CORE CONVERTER APPLICATION (Spans 2 columns) -->
                <div class="lg:col-span-2 flex flex-col gap-6">
                    <div class="glass p-8 rounded-2xl shadow-2xl relative overflow-hidden">
                        <div class="absolute top-0 left-0 w-full h-[3px] bg-gradient-to-r from-blue-500 to-indigo-500"></div>
                        
                        <div class="text-center mb-8">
                            <h2 class="text-2xl font-bold tracking-tight text-white mb-2">Download High-Definition Media</h2>
                            <p class="text-slate-400 text-sm">Paste your media link below to automatically extract and compile video and audio layers.</p>
                        </div>
                        
                        <!-- Input Element Field -->
                        <div class="flex flex-col md:flex-row gap-3 mb-6">
                            <div class="relative flex-1">
                                <input id="videoUrl" type="text" placeholder="Paste link from YouTube, TikTok, Instagram, Vimeo..." 
                                       class="w-full pl-4 pr-4 py-3.5 bg-slate-900/90 border border-slate-700 rounded-xl focus:outline-none focus:border-blue-500 text-slate-100 transition placeholder:text-slate-500 font-medium text-sm shadow-inner">
                            </div>
                            <button onclick="fetchOptions()" class="px-7 py-3.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-600 font-semibold rounded-xl transition shadow-lg shadow-blue-500/10 active:scale-[0.98]">
                                Analyze Link
                            </button>
                        </div>
                        
                        <!-- Dynamic Status Tracker -->
                        <div id="status" class="hidden text-center text-slate-300 py-3 bg-slate-900/40 rounded-xl border border-slate-800 text-sm font-medium animate-pulse">
                            Processing system operations...
                        </div>
                        
                        <!-- Results Stream Array -->
                        <div id="result" class="hidden border-t border-slate-800 pt-6 mt-2">
                            <div class="flex flex-col sm:flex-row gap-4 p-4 bg-slate-900/50 border border-slate-800 rounded-xl mb-4 items-center sm:items-start">
                                <img id="thumb" class="w-32 h-20 object-cover rounded-lg bg-slate-900 border border-slate-700" src="" alt="Thumbnail">
                                <div class="text-center sm:text-left">
                                    <span class="inline-block bg-blue-500/10 text-blue-400 text-[11px] font-bold px-2 py-0.5 rounded mb-1.5 uppercase tracking-wide">Ready</span>
                                    <h3 id="videoTitle" class="font-medium text-sm text-slate-200 line-clamp-2"></h3>
                                </div>
                            </div>
                            <div id="linksContainer" class="space-y-2.5 max-h-64 overflow-y-auto pr-1"></div>
                        </div>
                    </div>

                    <!-- Platform Trust Badge Grid -->
                    <div class="grid grid-cols-4 gap-2 text-center text-[11px] font-semibold tracking-wider text-slate-500 uppercase">
                        <div class="bg-slate-800/20 py-2.5 rounded-lg border border-slate-800/40">YouTube</div>
                        <div class="bg-slate-800/20 py-2.5 rounded-lg border border-slate-800/40">TikTok</div>
                        <div class="bg-slate-800/20 py-2.5 rounded-lg border border-slate-800/40">Instagram</div>
                        <div class="bg-slate-800/20 py-2.5 rounded-lg border border-slate-800/40">Vimeo</div>
                    </div>
                </div>

                <!-- RIGHT SIDEBAR AD SLOT (Right Side on Desktop) -->
                <div class="flex flex-col gap-4 bg-slate-800/30 border border-dashed border-slate-700/60 rounded-2xl p-4 text-center text-xs text-slate-500 min-h-[400px] lg:min-h-[500px] items-center justify-center">
                    <div class="ad-placeholder">
                        <p class="uppercase text-[10px] text-blue-500/60 font-bold mb-1">Advertisement</p>
                        <p>Square or Native Ad Block</p>
                        <p class="text-[11px] text-slate-600 mt-2">300 x 250 / 336 x 280</p>
                    </div>
                </div>

            </div>
        </main>

        <!-- FOOTER BRAND & AD PROFILE -->
        <footer class="w-full max-w-7xl mx-auto px-6 py-6 border-t border-slate-800/60 flex flex-col md:flex-row items-center justify-between text-xs text-slate-500 gap-4 mt-8">
            <p>&copy; 2026 EasyDownloader. High-speed media processing engine. For personal backup usage only.</p>
            <div class="flex gap-4 font-medium">
                <a href="#" class="hover:text-slate-300 transition">Privacy Policy</a>
                <a href="#" class="hover:text-slate-300 transition">Terms of Service</a>
                <a href="#" class="hover:text-slate-300 transition">API Documentation</a>
            </div>
        </footer>

        <!-- FUNCTIONAL CLIENT SCRIPTS -->
        <script>
            let currentUrl = "";

            async function fetchOptions() {
                const url = document.getElementById('videoUrl').value;
                if(!url) return alert("Please paste a target link URL first!");
                currentUrl = url;

                const status = document.getElementById('status');
                const result = document.getElementById('result');
                const linksContainer = document.getElementById('linksContainer');
                
                status.innerText = "Extracting stream layouts from web nodes...";
                status.classList.remove('hidden');
                result.classList.add('hidden');
                linksContainer.innerHTML = '';

                try {
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url })
                    });
                    const data = await response.json();
                    if(!response.ok) throw new Error(data.detail || "Failed to compile structure configurations.");
                    
                    document.getElementById('thumb').src = data.thumbnail || '';
                    document.getElementById('videoTitle').innerText = data.title;
                    
                    data.formats.forEach(format => {
                        const btn = document.createElement('button');
                        btn.className = "group flex justify-between items-center bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/40 px-4 py-3.5 rounded-xl text-sm transition font-medium w-full text-left";
                        btn.onclick = () => triggerDownload(format.format_id, format.ext);
                        btn.innerHTML = `
                            <div class="flex items-center gap-2.5">
                                <svg class="w-4 h-4 text-blue-400 group-hover:scale-110 transition" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                <span>Download Ready <span class="text-slate-400 text-xs ml-1">(${format.resolution})</span></span>
                            </div> 
                            <span class="text-blue-400 font-semibold text-xs bg-blue-500/10 px-2.5 py-1 rounded-md border border-blue-500/20 group-hover:bg-blue-500 group-hover:text-white transition uppercase tracking-wider text-[10px]">Stitch & Save</span>
                        `;
                        linksContainer.appendChild(btn);
                    });
                    result.classList.remove('hidden');
                } catch (err) {
                    alert(err.message);
                } finally {
                    status.classList.add('hidden');
                }
            }

            async function triggerDownload(formatId, ext) {
                const status = document.getElementById('status');
                status.innerText = "Running programmatic FFmpeg compilation matrix... (This can take 10-30 seconds)";
                status.classList.remove('hidden');

                try {
                    const response = await fetch('/api/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url: currentUrl, format_id: formatId, ext: ext })
                    });
                    if(!response.ok) {
                        const errData = await response.json();
                        throw new Error(errData.detail || "Track mixing error occurred.");
                    }
                    
                    const blob = await response.blob();
                    const downloadUrl = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = downloadUrl;
                    a.download = `EasyDownloader_${Date.now()}.${ext}`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                } catch(err) {
                    alert(err.message);
                } finally {
                    status.classList.add('hidden');
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/analyze")
async def analyze_video(request: AnalyzeRequest):
    ydl_opts = {'skip_download': True, 'quiet': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.url, download=False)
            formats = info.get('formats', [])
            seen_resolutions = set()
            available_formats = []

            for f in formats[::-1]:
                res = f.get('height')
                if res and f.get('vcodec') != 'none':
                    res_str = f"{res}p"
                    if res_str not in seen_resolutions:
                        seen_resolutions.add(res_str)
                        available_formats.append({
                            'format_id': f.get('format_id'),
                            'resolution': res_str,
                            'ext': 'mp4' if f.get('ext') == 'mp4' else f.get('ext') or 'mp4'
                        })
            
            return {
                "title": info.get('title', 'Video File'),
                "thumbnail": info.get('thumbnail'),
                "formats": available_formats
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/download")
async def download_and_merge(request: DownloadRequest):
    unique_id = str(uuid.uuid4())
    video_temp_path = os.path.join(DOWNLOAD_DIR, f"{unique_id}_video.tmp")
    audio_temp_path = os.path.join(DOWNLOAD_DIR, f"{unique_id}_audio.tmp")
    final_output_path = os.path.join(DOWNLOAD_DIR, f"{unique_id}_merged.{request.ext}")
    
    v_opts = {'format': request.format_id, 'outtmpl': video_temp_path, 'quiet': True}
    a_opts = {'format': 'bestaudio/best', 'outtmpl': audio_temp_path, 'quiet': True}
    
    try:
        with yt_dlp.YoutubeDL(v_opts) as ydl:
            ydl.download([request.url])
        with yt_dlp.YoutubeDL(a_opts) as ydl:
            ydl.download([request.url])
            
        current_folder = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_exe = os.path.join(current_folder, "ffmpeg.exe")
        
        if not os.path.exists(ffmpeg_exe):
            ffmpeg_exe = "ffmpeg"

        cmd = [
            ffmpeg_exe, "-y",
            "-i", video_temp_path,
            "-i", audio_temp_path,
            "-c:v", "copy",
            "-c:a", "aac",
            final_output_path
        ]
        
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if os.path.exists(video_temp_path): os.remove(video_temp_path)
        if os.path.exists(audio_temp_path): os.remove(audio_temp_path)

        if os.path.exists(final_output_path):
            return FileResponse(path=final_output_path, filename=f"EasyDownloader_{unique_id}.{request.ext}", media_type='video/mp4')
        else:
            raise HTTPException(status_code=500, detail=f"FFmpeg pipeline failure: {process.stderr}")
            
    except Exception as e:
        if os.path.exists(video_temp_path): os.remove(video_temp_path)
        if os.path.exists(audio_temp_path): os.remove(audio_temp_path)
        raise HTTPException(status_code=400, detail=str(e))