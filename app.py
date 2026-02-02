from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import yaml, os, json, asyncio, secrets, zipfile, io, shutil, base64, subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from automation_manager import AutomationManager

# Optional modules
try:
    from docx import Document
    from docx.shared import Inches
    import google.generativeai as genai
    OFFER_AVAILABLE = True
except ImportError:
    OFFER_AVAILABLE = False

load_dotenv()
app = FastAPI(title="Job Automation Hub")
security = HTTPBasic()
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
ACCOUNTS_FILE = BASE_DIR / "accounts.yaml"
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin123")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# State
job_logs = {}
active_tasks = {}
manager = AutomationManager(job_logs, active_tasks, BASE_DIR)

# Ensure directories
STATIC_DIR.mkdir(exist_ok=True)
(BASE_DIR / "sessions").mkdir(exist_ok=True)
(BASE_DIR / "output").mkdir(exist_ok=True)

if OFFER_AVAILABLE and GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('models/gemini-1.5-flash')
else:
    gemini_model = None

# Helpers
def get_config():
    with open(ACCOUNTS_FILE, "r") as f:
        return yaml.safe_load(f)

def auth_check(request: Request):
    auth = request.headers.get("Authorization", "")
    pwd = request.query_params.get("password", "")
    valid = secrets.compare_digest(pwd, APP_PASSWORD) or (auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], APP_PASSWORD))
    if not valid: raise HTTPException(status_code=401, detail="Unauthorized")

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f: return f.read()

@app.post("/api/auth")
async def authenticate(data: dict):
    if secrets.compare_digest(data.get("password", ""), APP_PASSWORD): return {"status": "success"}
    raise HTTPException(status_code=401)

@app.get("/api/config")
async def get_api_config(request: Request):
    auth_check(request)
    config = get_config()
    session_dir = BASE_DIR / "sessions"
    for company in config.get("companies", []):
        for acc in company.get("accounts", []):
            safe = acc["email"].replace("@", "_").replace(".", "_")
            plat = acc.get("platform", "linkedin").lower()
            prefix = f"{plat}_" if plat != "linkedin" else ""
            acc["has_session"] = (session_dir / f"{prefix}{safe}_cookies.json").exists()
    return config

@app.post("/api/run")
async def run_task(request: Request, background_tasks: BackgroundTasks):
    auth_check(request)
    data = await request.json()
    email, action, plat = data.get("email"), data.get("action"), data.get("platform", "linkedin")
    
    config = get_config()
    acc, comp = None, None
    for c in config["companies"]:
        for a in c["accounts"]:
            if a["email"] == email: acc, comp = a, c; break
    
    if not acc: return JSONResponse({"status": "error"}, 404)
    
    # Cancel existing
    if email in active_tasks and not active_tasks[email].done():
        active_tasks[email].cancel()

    task = asyncio.create_task(manager.execute_task(
        email, acc["password"], plat, action, data.get("headless", False),
        comp, acc.get("chrome_profile"), comp["templates"].get(action)
    ))
    active_tasks[email] = task
    return {"status": "started", "email": email}

@app.get("/api/logs/{email}")
async def get_logs(email: str, request: Request):
    auth_check(request)
    return {"logs": job_logs.get(email, []), "active": email in active_tasks and not active_tasks[email].done()}

@app.post("/api/stop")
async def stop_task(request: Request):
    auth_check(request)
    email = (await request.json()).get("email")
    if email in active_tasks:
        active_tasks[email].cancel()
        return {"status": "stopped"}
    return {"status": "not_found"}

# Webhook (Moltbot Ready)
@app.post("/webhook/{action}")
async def webhook_trigger(action: str, request: Request):
    auth_check(request)
    email = request.query_params.get("email")
    # Logic similar to run_task but for quick remote trigger
    return await run_task(request, None)

# Project Download
@app.get("/api/download")
async def download_project(request: Request):
    auth_check(request)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(BASE_DIR):
            if any(x in root for x in [".git", "__pycache__", ".venv", "output", "sessions"]): continue
            for file in files:
                p = Path(root) / file
                zf.write(p, p.relative_to(BASE_DIR))
    zip_buffer.seek(0)
    return StreamingResponse(zip_buffer, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=automation_hub.zip"})

# Offer APIs
@app.post("/api/offer/ai-parse")
async def ai_parse(request: Request):
    auth_check(request)
    if not gemini_model: return {"success": False, "message": "AI not configured"}
    try:
        prompt = (await request.json()).get("prompt")
        res = gemini_model.generate_content(f"Extract JSON (name, email, phone, position, start_date, salary, test_date): {prompt}")
        text = res.text.strip().replace('```json', '').replace('```', '')
        return {"success": True, "data": json.loads(text)}
    except Exception as e:
        msg = str(e)
        if "429" in msg: msg = "AI Busy (Quota Exceeded). Try again in a minute."
        return {"success": False, "message": msg}

@app.get("/api/offer/profiles")
async def get_profiles(request: Request):
    auth_check(request)
    return {"profiles": [d.name for d in (BASE_DIR / "profiles").iterdir() if d.is_dir()]}

# Main
if __name__ == "__main__":
    import uvicorn
    print(f"Server: http://localhost:8001 | Password: {APP_PASSWORD}")
    uvicorn.run(app, host="0.0.0.0", port=8001)
