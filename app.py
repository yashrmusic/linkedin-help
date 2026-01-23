from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import yaml
import os
import json
import asyncio
from linkedin_engine import LinkedInEngine
from pathlib import Path

app = FastAPI()
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
ACCOUNTS_FILE = BASE_DIR / "accounts.yaml"

# Ensure static directory exists
STATIC_DIR.mkdir(exist_ok=True)

# Global state for logs
job_logs = {}

def get_config():
    with open(ACCOUNTS_FILE, "r") as f:
        return yaml.safe_load(f)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return HTMLResponse("<h1>Error: static/index.html not found</h1>", status_code=404)
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return HTMLResponse(f"<h1>Error loading dashboard: {str(e)}</h1>", status_code=500)

@app.get("/api/config")
async def get_api_config():
    config = get_config()
    session_dir = BASE_DIR / "sessions"
    
    for company in config["companies"]:
        for account in company["accounts"]:
            email = account["email"]
            safe_email = email.replace("@", "_").replace(".", "_")
            cookies_file = session_dir / f"{safe_email}_cookies.json"
            account["has_session"] = cookies_file.exists()
            
    return config

@app.post("/api/run")
async def run_task(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    email = data.get("email")
    action = data.get("action")
    headless = data.get("headless", False)  # Default to False
    
    config = get_config()
    target_account = None
    target_company = None
    
    for company in config["companies"]:
        for account in company["accounts"]:
            if account["email"] == email:
                target_account = account
                target_company = company
                break
    
    if not target_account:
        return JSONResponse({"status": "error", "message": "Account not found"}, status_code=404)
    
    template = target_company["templates"].get(action, "Hello")
    
    # Run in background via asyncio task to allow cancellation
    if email in active_tasks and not active_tasks[email].done():
        return JSONResponse({"status": "error", "message": "Task already running for this account"}, status_code=400)

    task = asyncio.create_task(execute_linkedin_job(email, target_account["password"], template, action, headless))
    active_tasks[email] = task
    
    return {"status": "started", "email": email, "action": action, "headless": headless}

# Global state for logs and tasks
job_logs = {}
active_tasks = {}

@app.get("/api/logs/{email}")
async def get_target_logs(email: str):
    return {"logs": job_logs.get(email, [])}

@app.get("/api/analytics")
async def get_analytics():
    # Load messaged applicants
    messaged_file = BASE_DIR / "messaged_applicants.json"
    total_messaged = 0
    recent_activity = []
    
    if messaged_file.exists():
        try:
            with open(messaged_file, "r") as f:
                data = json.load(f)
                total_messaged = len(data)
                # Just take last 50 for now as "recent"
                recent_activity = list(reversed(data[-50:]))
        except: pass
        
    return {
        "total_messaged": total_messaged,
        "recent_activity": recent_activity
    }

@app.post("/api/stop")
async def stop_task(request: Request):
    data = await request.json()
    email = data.get("email")
    
    if email in active_tasks:
        task = active_tasks[email]
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        del active_tasks[email]
        return {"status": "stopped", "email": email}
    
    return {"status": "not_found", "message": "No active task for this account"}

async def execute_linkedin_job(email, password, template, action, headless):
    engine = LinkedInEngine(email, password, template, BASE_DIR)
    mode_str = "Headless" if headless else "Visible"
    job_logs[email] = [f"🚀 Starting {action} for {email} ({mode_str} Mode)..."]
    
    # Replace internal log function to update job_logs
    def custom_log(msg):
        engine.logs.append(msg)
        if email not in job_logs: job_logs[email] = []
        job_logs[email].append(msg)
    
    engine.log = custom_log
    
    try:
        if action == "invite_applicants":
            stats = await engine.run_invite_applicants(headless=headless)
            engine.log("🏁 Job Completed.")
            engine.log(f"Summary: {stats}")
        elif action == "post_job":
            await engine.run_post_job(headless=headless)
            engine.log("🏁 Job Completed.")
        elif action == "close_dead_jobs":
            await engine.run_close_jobs(headless=headless)
            engine.log("🏁 Job Completed.")
        else:
            engine.log(f"⚠️ Action {action} not yet implemented.")
            
    except asyncio.CancelledError:
        engine.log("🛑 Operation STOPPED by user request.")
        raise
    except Exception as e:
        engine.log(f"💥 Unexpected Error: {str(e)}")
    finally:
        # Cleanup if needed (browser close is handled in engine methods usually)
        if email in active_tasks:
            del active_tasks[email]

if __name__ == "__main__":
    import uvicorn
    # Create static dir if not exists
    (BASE_DIR / "static").mkdir(exist_ok=True)
    uvicorn.run(app, host="0.0.0.0", port=8001)
