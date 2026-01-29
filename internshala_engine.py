
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


class InternshalaEngine:
    """Engine for Internshala job/internship posting and management automation."""
    
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
            f.write(f"[INTERNSHALA:{self.email}] {message}\n")

    def _get_cookies_path(self):
        safe_email = self.email.replace("@", "_").replace(".", "_")
        return os.path.join(self.session_dir, f"internshala_{safe_email}_cookies.json")

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
        """Login to Internshala Employer."""
        self.log("🔐 Attempting Internshala login...")
        
        # Try loading existing session
        await self._load_cookies(context)
        
        # Go to employer dashboard
        await page.goto("https://internshala.com/employer/dashboard", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Check if already logged in
        if "login" not in page.url.lower():
            self.log("✅ Already logged in via saved session!")
            return True
        
        # Need to login
        await page.goto("https://internshala.com/employer/login", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Fill login form
        email_input = await page.query_selector('input[name="email"], input#email, input[type="email"]')
        password_input = await page.query_selector('input[name="password"], input#password, input[type="password"]')
        
        if email_input and password_input:
            await email_input.fill(self.email)
            await asyncio.sleep(0.5)
            await password_input.fill(self.password)
            await asyncio.sleep(0.5)
            
            # Click login button
            login_btn = await page.query_selector('button[type="submit"], #login_submit, button:has-text("Login")')
            if login_btn:
                await login_btn.click()
                await asyncio.sleep(5)
                
                # Save cookies on successful login
                if "login" not in page.url.lower():
                    await self._save_cookies(context)
                    self.log("✅ Login successful!")
                    return True
        
        self.log("❌ Login failed - check credentials")
        return False

    async def run_post_job(self, job_config=None, headless=False):
        """Post an internship on Internshala."""
        self.log(f"🚀 Starting Internshala Internship Post for {self.email}...")
        
        job_config = job_config or {
            "title": "Architecture Intern",
            "type": "internship",  # 'internship' or 'job'
            "stipend": "10000",
            "duration": "3 months",
            "location": "Delhi",
            "work_from_home": False,
            "skills": ["AutoCAD", "SketchUp", "3D Modeling"],
            "description": "We are looking for talented architecture interns to join our team."
        }
        
        p, browser, context, page = await self._launch_browser(headless)
        
        try:
            if not await self._login(page, context):
                return {"status": "error", "error": "Login failed"}
            
            # Navigate to Post Internship
            post_url = "https://internshala.com/employer/post_internship" if job_config.get("type") == "internship" else "https://internshala.com/employer/post_job"
            self.log(f"📋 Navigating to Post {job_config.get('type', 'internship').title()}...")
            await page.goto(post_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Fill internship title/profile
            title_input = await page.query_selector('input[name="profile"], input#profile, input[placeholder*="profile"]')
            if title_input:
                await title_input.fill(job_config["title"])
                await asyncio.sleep(1)
                # Select from dropdown if appears
                suggestion = await page.query_selector('.suggestion-item, .autocomplete-item, li[data-value]')
                if suggestion:
                    await suggestion.click()
                else:
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                self.log(f"✏️ Filled title: {job_config['title']}")
            
            # Skills
            skills_input = await page.query_selector('input[name="skill"], input#skill, input[placeholder*="skill"]')
            if skills_input:
                for skill in job_config.get("skills", [])[:3]:
                    await skills_input.fill(skill)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                self.log(f"🔧 Added skills: {', '.join(job_config.get('skills', [])[:3])}")
            
            # Work from home toggle
            if job_config.get("work_from_home"):
                wfh_toggle = await page.query_selector('input[name="work_from_home"], #work_from_home, label:has-text("Work from home")')
                if wfh_toggle:
                    await wfh_toggle.click()
                    self.log("🏠 Enabled Work from Home")
            else:
                # Fill location
                location_input = await page.query_selector('input[name="city"], input#city, input[placeholder*="city"]')
                if location_input:
                    await location_input.fill(job_config["location"])
                    await asyncio.sleep(1)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                    self.log(f"📍 Filled location: {job_config['location']}")
            
            # Stipend
            stipend_input = await page.query_selector('input[name="stipend"], input#stipend')
            if stipend_input:
                await stipend_input.fill(job_config.get("stipend", "10000"))
                self.log(f"💰 Filled stipend: {job_config.get('stipend', '10000')}")
            
            # Duration
            duration_select = await page.query_selector('select[name="duration"], select#duration')
            if duration_select:
                await duration_select.select_option(label=job_config.get("duration", "3 months"))
                self.log(f"📅 Set duration: {job_config.get('duration', '3 months')}")
            
            # Description
            desc_editor = await page.query_selector('textarea[name="description"], div.ql-editor, div[contenteditable="true"]')
            if desc_editor:
                tag = await desc_editor.evaluate("el => el.tagName")
                if tag.lower() == "textarea":
                    await desc_editor.fill(job_config["description"])
                else:
                    await desc_editor.click()
                    await page.keyboard.type(job_config["description"])
                self.log("📝 Filled description")
            
            self.log("⚠️ Internship posting form filled - manual review recommended before submit")
            await asyncio.sleep(5)
            
            # Take screenshot
            screenshot_path = os.path.join(self.base_dir, "debug_internshala_post.png")
            await page.screenshot(path=screenshot_path)
            self.log(f"📸 Screenshot saved: {screenshot_path}")
            
            return {"status": "success", "platform": "internshala", "job_title": job_config["title"]}
            
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return {"status": "error", "error": str(e)}
        finally:
            await browser.close()
            await p.stop()

    async def run_close_jobs(self, headless=False):
        """Close/Delete expired or inactive internships on Internshala."""
        self.log(f"🗑️ Starting Internshala Job Cleanup for {self.email}...")
        
        p, browser, context, page = await self._launch_browser(headless)
        stats = {"closed": 0, "active": 0, "jobs": []}
        
        try:
            if not await self._login(page, context):
                return {"status": "error", "error": "Login failed"}
            
            # Navigate to My Internships
            self.log("📋 Navigating to My Internships...")
            await page.goto("https://internshala.com/employer/internships", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Find all internship cards
            job_cards = await page.query_selector_all('.internship_item, .internship-card, [class*="internship-row"]')
            self.log(f"🔍 Found {len(job_cards)} internships to audit...")
            
            for i, card in enumerate(job_cards):
                try:
                    # Get job title
                    title_el = await card.query_selector('.profile, .title, h3, h4, a')
                    title = await title_el.inner_text() if title_el else f"Internship {i+1}"
                    
                    # Get status
                    status_el = await card.query_selector('.status, [class*="status"], .label')
                    status = await status_el.inner_text() if status_el else "Unknown"
                    
                    job_info = {"title": title.strip(), "status": status.strip()}
                    stats["jobs"].append(job_info)
                    
                    # Check if expired/closed
                    status_lower = status.lower()
                    if any(x in status_lower for x in ["expired", "closed", "paused", "inactive", "draft"]):
                        self.log(f"🗑️ Closing: {title} ({status})")
                        
                        # Click on the internship to open details/menu
                        menu_btn = await card.query_selector('.dropdown-toggle, .more-options, button[data-toggle]')
                        if menu_btn:
                            await menu_btn.click()
                            await asyncio.sleep(1)
                            
                            close_btn = await page.query_selector('a:has-text("Close"), a:has-text("Delete"), button:has-text("Close")')
                            if close_btn:
                                await close_btn.click()
                                await asyncio.sleep(1)
                                
                                # Confirm
                                confirm_btn = await page.query_selector('.confirm-btn, button:has-text("Yes"), button:has-text("Confirm")')
                                if confirm_btn:
                                    await confirm_btn.click()
                                    await asyncio.sleep(2)
                                    stats["closed"] += 1
                                    self.log(f"✅ Closed: {title}")
                    else:
                        stats["active"] += 1
                        self.log(f"✅ Active: {title}")
                        
                except Exception as e:
                    self.log(f"⚠️ Error processing internship: {str(e)}")
            
            self.log(f"🏁 Cleanup complete: {stats['closed']} closed, {stats['active']} active")
            return stats
            
        except Exception as e:
            self.log(f"❌ Error: {str(e)}")
            return {"status": "error", "error": str(e)}
        finally:
            await browser.close()
            await p.stop()

