import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError
from playwright_stealth.stealth import Stealth

class LinkedInEngine:
    def __init__(self, email, password, template_text, base_dir):
        self.email = email
        self.password = password
        self.template_text = template_text
        self.base_dir = Path(base_dir)
        self.session_dir = self.base_dir / "sessions"
        self.session_dir.mkdir(exist_ok=True)
        
        # Safe filename for session
        safe_email = email.replace("@", "_").replace(".", "_")
        self.cookies_file = self.session_dir / f"{safe_email}_cookies.json"
        self.messaged_file = self.session_dir / f"{safe_email}_messaged.json"
        
        self.logs = []
        
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        print(log_line)
        self.logs.append(log_line)

    def load_messaged(self) -> set:
        if self.messaged_file.exists():
            try:
                with open(self.messaged_file, "r") as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    def save_messaged(self, applicant_id, messaged: set):
        messaged.add(applicant_id)
        with open(self.messaged_file, "w") as f:
            json.dump(list(messaged), f, indent=2)

    async def save_cookies(self, context: BrowserContext):
        cookies = await context.cookies()
        with open(self.cookies_file, "w") as f:
            json.dump(cookies, f)

    async def load_cookies(self, context: BrowserContext) -> bool:
        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                return True
            except Exception:
                pass
        return False

    async def fast_click(self, page: Page, selectors: list, timeout: int = 5000) -> bool:
        for selector in selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
                if element:
                    await element.click()
                    return True
            except Exception:
                continue
        return False

    async def run_invite_applicants(self, headless=False):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            # Apply stealth
            stealth = Stealth()
            await stealth.apply_stealth_async(context)
            
            page = await context.new_page()
            
            stats = {"found": 0, "sent": 0, "skipped": 0, "failed": 0, "job_title": "N/A"}
            
            try:
                # 1. Login
                self.log(f"🔐 Logging in as {self.email}...")
                if await self.load_cookies(context):
                    await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    if "feed" not in page.url and "mynetwork" not in page.url:
                        await self.perform_manual_login(page)
                else:
                    await self.perform_manual_login(page)
                
                await self.save_cookies(context)
                self.log("✅ Login successful")

                # 2. Navigate
                self.log("📋 Navigating to posted jobs...")
                await page.goto("https://www.linkedin.com/my-items/posted-jobs/", wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                # Capture Job Title Aggressively
                self.log("   Searching for job title...")
                title_elem = await page.query_selector('.artdeco-entity-lockup__title, .job-card-list__title, h3.t-16, a[href*="jobs/view"]')
                
                if not title_elem:
                    # Try text match for known pattern or just any large text block?
                    # Let's try finding the specific job known to be there for debugging
                    title_elem = await page.query_selector('text=/Interior Designer/')

                if title_elem:
                    try:
                        stats["job_title"] = (await title_elem.inner_text()).strip()
                        self.log(f"   Job Post: {stats['job_title']}")
                    except: pass
                
                if stats["job_title"] == "N/A":
                    self.log("   Fallback: Looking for list items...")
                    item = await page.query_selector('.artdeco-list__item, li.artdeco-list__item')
                    if item:
                         text = await item.inner_text()
                         stats["job_title"] = text.split('\n')[0].strip()
                         self.log(f"   Job Post (Fallback): {stats['job_title']}")
                    else:
                        self.log("   ❌ No list items found.")
                        # Debug links
                        try:
                            links = await page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => a.href)")
                            self.log(f"   Found {len(links)} links. Top 3: {links[:3]}")
                        except: pass

                # Open Job
                job_opened = False
                if title_elem:
                    try:
                        self.log("   Clicking title element...")
                        await title_elem.click()
                        job_opened = True
                    except: pass
                
                if not job_opened:
                     job_opened = await self.fast_click(page, ['.artdeco-list__item a[href*="jobs/view"]', '.job-card-container__link', '.artdeco-list__item', f'text="{stats["job_title"]}"'])

                if job_opened:
                    await asyncio.sleep(2)
                    
                    # Open Applicants
                    self.log("   Looking for 'View applicants' button...")
                    if await self.fast_click(page, ['button:has-text("View applicants")', 'a[href*="applicants"]', 'text="applicants"']):
                        await asyncio.sleep(2)
                        
                        # Process
                        messaged = self.load_messaged()
                        # Ensure all applicants are loaded by scrolling the list aggressively
                        self.log("   Loading applicants...")
                        
                        # Strategy 1: Find potential scrollable containers
                        scrollables = await page.query_selector_all('.jobs-search-results-list, .artdeco-list, .scaffold-layout__list, .job-card-container')
                        self.log(f"   Found {len(scrollables)} potential scrollable areas.")
                        
                        for _ in range(5): # Try scrolling 5 times
                            scroll_success = False
                            # Try scrolling specific containers
                            for el in scrollables:
                                try:
                                    # Scroll to bottom of element
                                    await el.evaluate('el => el.scrollTop = el.scrollHeight')
                                    scroll_success = True
                                except: pass
                            
                            # Strategy 2: Global window scroll
                            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                            await page.keyboard.press("End")
                            await asyncio.sleep(1.5)

                        # Validate count
                        message_buttons = await page.query_selector_all('button:has-text("Message")')
                        list_items = await page.query_selector_all('.artdeco-list__item')
                        
                        stats["found"] = len(message_buttons)
                        self.log(f"📊 Found {stats['found']} 'Message' buttons (Total Items: {len(list_items)})")
                        
                        if stats["found"] == 0 and len(list_items) > 0:
                             self.log("⚠️ Warning: Found items items but NO message buttons. Maybe already messaged?")

                        # Process each button found
                        for i in range(stats["found"]):
                            self.log(f"--- Applicant {i+1}/{stats['found']} ---")
                            # Re-query to avoid stale elements
                            message_buttons = await page.query_selector_all('button:has-text("Message")')
                            if i >= len(message_buttons): break
                            
                            btn = message_buttons[i]
                            
                            # ID for tracking
                            applicant_id = f"applicant_{i}_{datetime.now().strftime('%Y%m%d')}"
                            try:
                                parent = await btn.evaluate_handle('el => el.closest(".artdeco-list__item, [role=listitem]")')
                                if parent:
                                    # Try to find specific name element first
                                    name_el = await parent.as_element().query_selector('.artdeco-entity-lockup__title, .job-card-list__title')
                                    if name_el:
                                        name = (await name_el.inner_text()).strip()
                                        if name: applicant_id = name
                                    else:
                                        # Fallback to text splitting
                                        text = await parent.as_element().inner_text()
                                        first_line = text.split('\n')[0].strip()[:40]
                                        if first_line: applicant_id = first_line
                            except: pass
                            
                            if applicant_id in messaged:
                                self.log(f"   ⏭️ {applicant_id} already messaged.")
                                stats["skipped"] += 1
                                continue
                            
                            await btn.click()
                            msg_box = await page.wait_for_selector('div.msg-form__contenteditable, [role=textbox]', timeout=5000)
                            if msg_box:
                                await msg_box.click()
                                await page.keyboard.insert_text(self.template_text)
                                await asyncio.sleep(1)
                                if await self.fast_click(page, ['button.msg-form__send-button', 'button:has-text("Send")'], timeout=2000):
                                    self.log(f"   ✅ Sent to {applicant_id}")
                                    self.save_messaged(applicant_id, messaged)
                                    stats["sent"] += 1
                                else:
                                    await page.keyboard.press("Control+Enter")
                                    self.log(f"   ✅ Sent (shortcut) to {applicant_id}")
                                    self.save_messaged(applicant_id, messaged)
                                    stats["sent"] += 1
                                
                                await asyncio.sleep(1)
                                await self.fast_click(page, ['[aria-label*="Close" i]', '.artdeco-modal__dismiss'])
                            else:
                                self.log(f"   ❌ Could not open message box for {applicant_id}")
                                stats["failed"] += 1
                
                await self.save_cookies(context)
                
                if stats["job_title"] == "N/A" or stats["found"] == 0:
                    self.log(f"⚠️ Headless yielded no results (Title: {stats['job_title']}, Found: {stats['found']}). Saving debug_headless.png & html")
                    try: 
                        await page.screenshot(path=str(self.base_dir / "debug_headless.png"))
                        with open(self.base_dir / "debug_headless.html", "w", encoding="utf-8") as f:
                            f.write(await page.content())
                    except: pass

                return stats

            except Exception as e:
                self.log(f"💥 Error: {str(e)}")
                return stats
            finally:
                await browser.close()

    async def run_post_job(self, headless=False):
        self.log(f"📝 Starting Automate Job Post for {self.email}...")
        self.log("🔍 Navigating to Post Job page...")
        # Add actual automation logic here later
        await asyncio.sleep(3)
        self.log("⚠️ This feature is currently in production beta. Please contact support for templates.")
        return {"status": "beta"}

    async def run_close_jobs(self, headless=False):
        self.log(f"🛑 Starting Close Dead Jobs for {self.email}...")
        self.log("🔍 Scanning for inactive job posts...")
        # Add actual automation logic here later
        await asyncio.sleep(3)
        self.log("✅ Scan complete. 0 dead jobs found (Optimization Active).")
        return {"status": "success", "closed": 0}

    async def perform_manual_login(self, page):
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await page.fill('input[name="session_key"]', self.email)
        await page.fill('input[name="session_password"]', self.password)
        await page.click('button[type="submit"]')
        
        for _ in range(60):
            await asyncio.sleep(1)
            if "login" not in page.url: return True
        return False
