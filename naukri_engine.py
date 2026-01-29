
import asyncio
import os
import json
from datetime import datetime
from playwright.async_api import async_playwright

# Import stealth - the library uses 'stealth' for both sync and async
from playwright_stealth import stealth

async def stealth_async(page):
    """Apply stealth to async page."""
    await asyncio.to_thread(lambda: None)  # Yield to event loop
    stealth(page)


class NaukriEngine:
    """Engine for Naukri.com job posting and management automation."""
    
    def __init__(self, email, password, company_name="", base_dir=None):
        self.email = email
        self.password = password
        self.company_name = company_name
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(__file__))
        self.logs = []
        self.session_dir = os.path.join(self.base_dir, "sessions")
        os.makedirs(self.session_dir, exist_ok=True)

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        self.logs.append(message)
        log_file = os.path.join(self.base_dir, "run_log.txt")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[NAUKRI:{self.email}] {message}\n")

    def _get_cookies_path(self):
        safe_email = self.email.replace("@", "_").replace(".", "_")
        return os.path.join(self.session_dir, f"naukri_{safe_email}_cookies.json")

    async def _save_cookies(self, context):
        cookies = await context.cookies()
        with open(self._get_cookies_path(), "w") as f:
            json.dump(cookies, f)
        self.log("💾 Session cookies saved.")

    async def _load_cookies(self, context):
        cookies_path = self._get_cookies_path()
        if os.path.exists(cookies_path):
            with open(cookies_path, "r") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            self.log("🍪 Loaded existing session cookies.")
            return True
        return False

    async def _launch_browser(self, headless=False):
        """Launch browser with stealth mode."""
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=headless, 
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await stealth_async(page)
        return p, browser, context, page

    async def _login(self, page, context):
        """Login to Naukri Recruiter."""
        self.log("🔐 Attempting Naukri login...")
        
        # Try loading existing session
        await self._load_cookies(context)
        
        # Go to recruiter dashboard
        await page.goto("https://recruiter.naukri.com/", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Check if already logged in
        if "login" not in page.url.lower() and await page.query_selector('text=Post a Job'):
            self.log("✅ Already logged in via saved session!")
            return True
        
        # Need to login
        await page.goto("https://recruiter.naukri.com/recruiterLogin", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Fill login form
        email_input = await page.query_selector('input[type="text"][placeholder*="Email"], input[name="username"], input#usernameField')
        password_input = await page.query_selector('input[type="password"]')
        
        if email_input and password_input:
            await email_input.fill(self.email)
            await asyncio.sleep(0.5)
            await password_input.fill(self.password)
            await asyncio.sleep(0.5)
            
            # Click login button
            login_btn = await page.query_selector('button[type="submit"], button:has-text("Login")')
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(5)
                
                # Save cookies on successful login
                if "login" not in page.url.lower():
                    await self._save_cookies(context)
                    self.log("✅ Login successful!")
                    return True
        
        self.log("❌ Login failed - check credentials or complete CAPTCHA manually")
        return False

    async def run_post_job(self, job_config=None, headless=False):
        """Post a new job on Naukri."""
        self.log(f"🚀 Starting Naukri Job Post for {self.email}...")
        
        job_config = job_config or {
            "title": "Architect",
            "location": "Delhi",
            "experience_min": 0,
            "experience_max": 2,
            "salary_min": 150000,
            "salary_max": 300000,
            "description": "We are looking for talented architects to join our team."
        }
        
        p, browser, context, page = await self._launch_browser(headless)
        
        try:
            if not await self._login(page, context):
                return {"status": "error", "error": "Login failed"}
            
            # Navigate to Post Job
            self.log("📋 Navigating to Post Job...")
            await page.goto("https://recruiter.naukri.com/job-posting/new", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Fill job title
            title_input = await page.query_selector('input[placeholder*="Job Title"], input[name="designation"]')
            if title_input:
                await title_input.fill(job_config["title"])
                self.log(f"✏️ Filled job title: {job_config['title']}")
            
            # Fill location
            location_input = await page.query_selector('input[placeholder*="Location"], input[name="location"]')
            if location_input:
                await location_input.fill(job_config["location"])
                await asyncio.sleep(1)
                # Select from dropdown
                await page.keyboard.press("ArrowDown")
                await page.keyboard.press("Enter")
                self.log(f"📍 Filled location: {job_config['location']}")
            
            # Fill experience
            exp_min = await page.query_selector('input[name="minExperience"], select[name="minExp"]')
            if exp_min:
                if await exp_min.get_attribute("type") == "select":
                    await exp_min.select_option(str(job_config["experience_min"]))
                else:
                    await exp_min.fill(str(job_config["experience_min"]))
            
            # Fill description
            desc_editor = await page.query_selector('div[contenteditable="true"], textarea[name="jobDescription"]')
            if desc_editor:
                await desc_editor.click()
                await page.keyboard.type(job_config["description"])
                self.log("📝 Filled job description")
            
            self.log("⚠️ Job posting form filled - manual review recommended before submit")
            await asyncio.sleep(5)  # Give time to review
            
            # Take screenshot for debugging
            screenshot_path = os.path.join(self.base_dir, "debug_naukri_post.png")
            await page.screenshot(path=screenshot_path)
            self.log(f"📸 Screenshot saved: {screenshot_path}")
            
            return {"status": "success", "platform": "naukri", "job_title": job_config["title"]}
            
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return {"status": "error", "error": str(e)}
        finally:
            await browser.close()
            await p.stop()

    async def run_delete_jobs(self, headless=False):
        """Delete/Close expired or paused jobs on Naukri."""
        self.log(f"🗑️ Starting Naukri Job Cleanup for {self.email}...")
        
        p, browser, context, page = await self._launch_browser(headless)
        stats = {"deleted": 0, "active": 0, "jobs": []}
        
        try:
            if not await self._login(page, context):
                return {"status": "error", "error": "Login failed"}
            
            # Navigate to My Jobs
            self.log("📋 Navigating to My Jobs...")
            await page.goto("https://recruiter.naukri.com/job-posting/manage", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Find all job cards
            job_cards = await page.query_selector_all('.job-card, .jobTuple, [data-job-id]')
            self.log(f"🔍 Found {len(job_cards)} jobs to audit...")
            
            for i, card in enumerate(job_cards):
                try:
                    # Get job title
                    title_el = await card.query_selector('.job-title, .jobTitle, h3, h4')
                    title = await title_el.inner_text() if title_el else f"Job {i+1}"
                    
                    # Get job status
                    status_el = await card.query_selector('.status, .jobStatus, [class*="status"]')
                    status = await status_el.inner_text() if status_el else "Unknown"
                    
                    job_info = {"title": title.strip(), "status": status.strip()}
                    stats["jobs"].append(job_info)
                    
                    # Check if job is expired/paused
                    status_lower = status.lower()
                    if any(x in status_lower for x in ["expired", "paused", "closed", "inactive"]):
                        self.log(f"🗑️ Deleting: {title} ({status})")
                        
                        # Click more options / delete
                        more_btn = await card.query_selector('button[aria-label*="more"], .more-options, [class*="menu"]')
                        if more_btn:
                            await more_btn.click()
                            await asyncio.sleep(1)
                            
                            delete_btn = await page.query_selector('text=Delete, text=Remove, button:has-text("Delete")')
                            if delete_btn:
                                await delete_btn.click()
                                await asyncio.sleep(1)
                                
                                # Confirm deletion
                                confirm_btn = await page.query_selector('button:has-text("Confirm"), button:has-text("Yes")')
                                if confirm_btn:
                                    await confirm_btn.click()
                                    await asyncio.sleep(2)
                                    stats["deleted"] += 1
                                    self.log(f"✅ Deleted: {title}")
                    else:
                        stats["active"] += 1
                        self.log(f"✅ Active: {title}")
                        
                except Exception as e:
                    self.log(f"⚠️ Error processing job: {str(e)}")
            
            self.log(f"🏁 Cleanup complete: {stats['deleted']} deleted, {stats['active']} active")
            return stats
            
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return {"status": "error", "error": str(e)}
        finally:
            await browser.close()
            await p.stop()
