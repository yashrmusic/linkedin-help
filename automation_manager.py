import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from linkedin_engine import LinkedInEngine
from internshala_engine import InternshalaEngine
from naukri_engine import NaukriEngine

class AutomationManager:
    def __init__(self, job_logs, active_tasks, base_dir):
        self.job_logs = job_logs
        self.active_tasks = active_tasks
        self.base_dir = base_dir

    async def execute_task(self, email, password, platform, action, headless, company_config, chrome_profile=None, template=None):
        """Unified executor for cross-platform automation."""
        safe_email = email.replace("@", "_").replace(".", "_")
        
        # Initialize engine
        if platform == "linkedin":
            engine = LinkedInEngine(email, password, template, self.base_dir, chrome_profile=chrome_profile or "Default")
        elif platform == "internshala":
            engine = InternshalaEngine(email, password, company_config.get("name", ""), self.base_dir)
        elif platform == "naukri":
            engine = NaukriEngine(email, password, company_config.get("name", ""), self.base_dir)
        else:
            raise ValueError(f"Unknown platform: {platform}")

        # Setup logging
        if email not in self.job_logs:
            self.job_logs[email] = []
        
        def custom_log(msg):
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {msg}"
            self.job_logs[email].append(log_entry)
            print(f"[{platform.upper()}] {log_entry}")
            
        engine.log = custom_log
        
        try:
            mode_str = "Headless" if headless else "Visible"
            engine.log(f"Initializing {action} ({mode_str})...")
            
            if platform == "linkedin":
                if action == "invite_applicants":
                    await engine.run_invite_applicants(headless=headless)
                elif action == "post_job":
                    await engine.run_post_job(headless=headless, company_config=company_config)
                elif action == "close_dead_jobs":
                    await engine.run_close_jobs(headless=headless)
                elif action == "maintain_active_job":
                    engine.log("PHASE 1: Auditing current jobs...")
                    audit_stats = await engine.run_close_jobs(headless=headless)
                    if audit_stats.get("active", 0) > 0:
                        engine.log(f"Active job verified: {audit_stats['jobs'][0]['title']}")
                    else:
                        engine.log("PHASE 2: No active jobs. Posting new slot...")
                        await engine.run_post_job(headless=headless, company_config=company_config)
                else:
                    engine.log(f"Action {action} not implemented.")
            
            elif platform == "internshala":
                if action == "post_job":
                    job_config = {
                        "title": company_config.get("job_titles", ["Architecture Intern"])[0],
                        "type": "internship",
                        "location": company_config.get("default_location", "Delhi"),
                        "description": f"Join {company_config['name']}!"
                    }
                    await engine.run_post_job(job_config=job_config, headless=headless)
                elif action == "close_dead_jobs" or action == "delete_jobs":
                    await engine.run_close_jobs(headless=headless)
                else:
                    engine.log(f"Action {action} not implemented.")

            elif platform == "naukri":
                if action == "post_job":
                    job_config = {
                        "title": company_config.get("job_titles", ["Architect"])[0],
                        "location": company_config.get("default_location", "Delhi"),
                        "description": f"Join {company_config['name']}!"
                    }
                    await engine.run_post_job(job_config=job_config, headless=headless)
                elif action == "close_dead_jobs" or action == "delete_jobs":
                    await engine.run_delete_jobs(headless=headless)
                else:
                    engine.log(f"Action {action} not implemented.")

            engine.log("Cycle completed successfully.")

        except asyncio.CancelledError:
            engine.log("STOPPED by user request.")
            raise
        except Exception as e:
            engine.log(f"Error: {str(e)}")
        finally:
            if email in self.active_tasks:
                del self.active_tasks[email]
