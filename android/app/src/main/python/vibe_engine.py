import asyncio
import json
import os
import sys
import uuid
import zipfile
import socket
import threading
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# --- ANDROID PATHS ---
try:
    from com.chaquo.python import Python
    ANDROID_CONTEXT = Python.getPlatform().getApplication()
    INTERNAL_STORAGE = str(ANDROID_CONTEXT.getFilesDir())
    BASE_DIR = Path(INTERNAL_STORAGE)
except:
    BASE_DIR = Path(__file__).resolve().parent

DOWNLOAD_DIR = BASE_DIR / "downloads"
ARCHIVE_DIR = BASE_DIR / "archives"
CONFIG_FILE = BASE_DIR / "vibe-config.json"

for d in [DOWNLOAD_DIR, ARCHIVE_DIR]: d.mkdir(exist_ok=True)

# --- CONFIG ---
DEFAULT_CONFIG = {
    "title": "Vibe Mobile",
    "tagline": "Standalone Phone Engine",
    "accent": "#ff2e88",
    "bg": "#050505",
    "port": 8080
}

SITE_CONFIG = DEFAULT_CONFIG.copy()
JOBS: Dict[str, dict] = {}

app = FastAPI(title="Vibe Mobile")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")

# --- ENGINE ---
async def run_spotdl(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}

    # On Android, we must call 'python' as 'sys.executable'
    # We use -m spotdl to run the installed module
    cmd = [sys.executable, "-m", "spotdl", "download", query, "--output", str(DOWNLOAD_DIR / "{artist} - {title}.{output-ext}")]

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        assert proc.stdout
        while True:
            line = await proc.stdout.readline()
            if not line: break
            msg = line.decode(errors='replace').strip()
            if msg:
                job["log"].append(msg)
                job["log"] = job["log"][-100:]
        rc = await proc.wait()
        job["status"] = "complete" if rc == 0 else "failed"
        if rc == 0:
            after = {f.name for f in DOWNLOAD_DIR.glob("*")}
            new_files = list(after - before)
            if new_files:
                zip_name = f"Vibe_{job_id[:8]}.zip"
                with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
                    for f in new_files: zf.write(DOWNLOAD_DIR / f, arcname=f)
                job["zip_url"] = f"{base_url}/archives/{zip_name}"
    except Exception as e:
        job["status"] = "failed"; job["log"].append(f"Error: {str(e)}")

# --- API ---
@app.get("/api/health")
async def health(): return {"status": "ok", "mode": "standalone"}

@app.get("/api/config_data")
async def get_cfg(): return SITE_CONFIG

@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    base_url = str(request.base_url).rstrip('/')
    JOBS[job_id] = {"id": job_id, "query": query, "status": "queued", "log": ["Engine starting..."], "zip_url": None}
    asyncio.create_task(run_spotdl(job_id, query, base_url))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): return JOBS.get(job_id, {"status": "not_found", "log": []})

@app.get("/api/files")
async def list_files(request: Request):
    base_url = str(request.base_url).rstrip('/')
    files = []
    for p in sorted(ARCHIVE_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({"name": p.name, "url": f"{base_url}/archives/{p.name}", "type": "zip", "size": p.stat().st_size})
    for p in sorted(DOWNLOAD_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and not p.name.startswith('.'):
            files.append({"name": p.name, "url": f"{base_url}/downloads/{p.name}", "type": "mp3", "size": p.stat().st_size})
    return {"files": files[:50]}

# --- UI ---
@app.get("/", response_class=HTMLResponse)
async def index():
    c = SITE_CONFIG
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>Vibe Standalone</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ background-color: {c['bg']}; color: white; font-family: sans-serif; }}
        .glass {{ background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }}
    </style>
</head>
<body class="p-6">
    <h1 class="text-3xl font-black mb-2">{c['title']}</h1>
    <p class="text-xs opacity-50 mb-8">{c['tagline']}</p>

    <div class="glass p-4 rounded-2xl mb-6">
        <input type="text" id="q" placeholder="Spotify Link..." class="w-full bg-transparent outline-none text-lg mb-4">
        <button onclick="dl()" class="w-full py-3 rounded-xl font-bold text-black" style="background: {c['accent']};">Download</button>
    </div>

    <div id="status" class="hidden glass p-4 rounded-2xl mb-6">
        <p id="st" class="text-xs font-bold text-cyan-400 mb-2">QUEUED</p>
        <div id="log" class="text-[10px] font-mono opacity-50 h-32 overflow-y-auto whitespace-pre-wrap"></div>
    </div>

    <div id="files" class="space-y-2"></div>

    <script>
        async function dl() {{
            const q = document.getElementById('q').value;
            const fd = new FormData(); fd.append('query', q);
            const res = await fetch('/api/download', {{method:'POST', body:fd}});
            const data = await res.json();
            document.getElementById('status').classList.remove('hidden');
            poll(data.job_id);
        }}
        async function poll(id) {{
            const res = await fetch('/api/jobs/'+id);
            const job = await res.json();
            document.getElementById('st').innerText = job.status.toUpperCase();
            document.getElementById('log').innerText = job.log.join('\\n');
            const log = document.getElementById('log'); log.scrollTop = log.scrollHeight;
            if(job.status==='running'||job.status==='queued') setTimeout(()=>poll(id), 1000);
            else refresh();
        }}
        async function refresh() {{
            const res = await fetch('/api/files');
            const data = await res.json();
            document.getElementById('files').innerHTML = data.files.map(f => `<a href="${{f.url}}" class="block glass p-3 rounded-xl text-xs truncate">${{f.name}}</a>`).join('');
        }}
        refresh();
    </script>
</body>
</html>
"""

def start_server():
    """Function called from Kotlin to start the engine."""
    def run():
        print("Starting Vibe Mobile Server...")
        uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return "STARTED"
