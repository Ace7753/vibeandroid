import asyncio
import json
import os
import sys
import uuid
import zipfile
import socket
import shutil
from pathlib import Path
from typing import Dict, Set

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", str(BASE_DIR / "archives"))).resolve()
CONFIG_FILE = BASE_DIR / "vibe-config.json"
COOKIE_FILE = BASE_DIR / "cookies.txt"

for d in [DOWNLOAD_DIR, ARCHIVE_DIR]: d.mkdir(exist_ok=True)

# --- CONFIG ---
DEFAULT_CONFIG = {
    "title": "Vibe",
    "tagline": "Spotify Downloader",
    "accent": "#ff2e88",
    "bg": "#050505",
    "port": 8080
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try: config.update(json.loads(CONFIG_FILE.read_text()))
        except: pass
    return config

SITE_CONFIG = load_config()
JOBS: Dict[str, dict] = {}

app = FastAPI(title="Vibe")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")

# --- ENGINE ---
async def get_metadata(query: str):
    temp_meta = BASE_DIR / f"meta_{uuid.uuid4().hex}.spotdl"
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "spotdl", "save", query,
            "--save-file", str(temp_meta),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        if temp_meta.exists():
            data = json.loads(temp_meta.read_text())
            if isinstance(data, list) and data:
                first = data[0]
                if "/playlist/" in query: return "Playlist"
                if len(data) > 1: return f"{first.get('artist')} - {first.get('album_name')}"
                return f"{first.get('artist')} - {first.get('name')}"
    except: pass
    finally:
        if temp_meta.exists(): temp_meta.unlink()
    return "Vibe_Pack"

async def run_spotdl(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    zip_base = await get_metadata(query)
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}
    is_playlist = "/playlist/" in query
    output_template = "{list-position} - {artist} - {title}.{output-ext}" if is_playlist else "{artist} - {title}.{output-ext}"

    # NO-DENO STEALTH ENGINE CONFIG
    cmd = [
        sys.executable, "-m", "spotdl", "download", query,
        "--output", str(DOWNLOAD_DIR / output_template),
        "--format", "m4a",
        "--threads", "4",
        "--search-query", "{artist} - {title}",
        "--audio", "youtube-music", "piped", "soundcloud", "youtube",
        "--yt-dlp-args", "--impersonate chrome --geo-bypass --no-check-certificate --quiet"
    ]

    if is_playlist: cmd.append("--playlist-numbering")
    if COOKIE_FILE.exists(): cmd.extend(["--cookie-file", str(COOKIE_FILE)])

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        while True:
            line = await proc.stdout.readline()
            if not line: break
            msg = line.decode(errors='replace').strip()
            if msg: job["log"].append(msg); job["log"] = job["log"][-50:]
        rc = await proc.wait()
        job["status"] = "complete" if rc == 0 else "failed"
        if rc == 0:
            after = {f.name for f in DOWNLOAD_DIR.glob("*")}
            new = list(after - before)
            if new:
                safe = "".join([c for c in zip_base if c.isalnum() or c in (' ','-','_')]).strip()
                zip_name = f"{safe}_{job_id[:4]}.zip"
                with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
                    for f in new: zf.write(DOWNLOAD_DIR / f, arcname=f)
                job["zip_url"] = f"{base_url}/archives/{zip_name}"
    except Exception as e: job["status"] = "failed"; job["log"].append(str(e))

# --- API ---
@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    base_url = str(request.base_url).rstrip('/')
    JOBS[job_id] = {"id": job_id, "query": query, "status": "queued", "log": ["Engine starting (No-Deno Mode)..."], "zip_url": None}
    asyncio.create_task(run_spotdl(job_id, query, base_url))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): return JOBS.get(job_id, {"status": "not_found", "log": []})

@app.post("/api/clear")
async def clear_downloads():
    for f in [DOWNLOAD_DIR, ARCHIVE_DIR]:
        for i in f.glob("*"):
            if i.is_file(): i.unlink()
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def index():
    c = SITE_CONFIG
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{c['title']}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background: {c['bg']}; color: white; font-family: sans-serif; padding: 20px; }}
        .btn {{ background: {c['accent']}; color: black; padding: 10px; border-radius: 5px; text-decoration: none; display: inline-block; border: none; cursor: pointer; }}
    </style>
</head>
<body>
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <img src="/assets/vibe_icon_original.png" style="width:50px; height:50px; border-radius:10px; margin-right:15px;">
        <h1 style="flex:1;">{c['title']}</h1>
        <button onclick="clearAll()" class="btn" style="background:#444; color:white; font-size:10px;">CLEAR ALL</button>
    </div>
    <p>{c['tagline']}</p>
    <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px;">
        <input type="text" id="q" placeholder="Spotify Link" style="width: 70%; padding: 10px;">
        <button onclick="dl()" class="btn">Download</button>
    </div>
    <div id="status" style="margin-top:20px; font-weight:bold;">READY</div>
    <a id="pack" href="#" style="display:none; margin-top:20px;" class="btn">📦 Download Pack Your Files</a>
    <script>
        async function dl() {{
            const q = document.getElementById('q').value;
            document.getElementById('status').innerText = 'Starting...';
            const fd = new FormData(); fd.append('query', q);
            const res = await fetch('/api/download', {{method:'POST', body:fd}});
            const data = await res.json();
            poll(data.job_id);
        }}
        async function poll(id) {{
            const res = await fetch('/api/jobs/'+id);
            const job = await res.json();
            document.getElementById('status').innerText = job.status;
            if(job.status === 'complete') {{
                if(job.zip_url) {{
                    const p = document.getElementById('pack');
                    p.href = job.zip_url; p.style.display = 'block';
                }}
            }} else if(job.status !== 'failed') {{
                setTimeout(() => poll(id), 1000);
            }}
        }}
        async function clearAll() {{ if(confirm('Clear all?')) await fetch('/api/clear', {{method:'POST'}}); alert('Cleared'); location.reload(); }}
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
