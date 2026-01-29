import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError
from playwright_stealth.stealth import Stealth

class LinkedInEngine:
    def __init__(self, email, password, template_text, base_dir, chrome_profile="Default"):
        self.email = email
        self.password = password
        self.template_text = template_text
        self.base_dir = Path(base_dir)
        self.session_dir = self.base_dir / "sessions"
        self.session_dir.mkdir(exist_ok=True)
        
        # Chrome profile config
        self.chrome_profile = chrome_profile
        self.chrome_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
        self.chrome_exe = self._find_chrome_executable()
        
        # Safe filename for session
        safe_email = email.replace("@", "_").replace(".", "_")
        self.cookies_file = self.session_dir / f"{safe_email}_cookies.json"
        self.messaged_file = self.session_dir / f"{safe_email}_messaged.json"
        
        self.logs = []
    
    def _find_chrome_executable(self):
        """Find Chrome executable on Windows."""
        possible_paths = [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None  # Will fall back to Playwright's bundled Chromium
        
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
        self.log(f"   Using Chrome profile: {self.chrome_profile}")
        
        async with async_playwright() as p:
            # Use real Chrome with persistent profile to avoid detection
            if self.chrome_exe and os.path.exists(self.chrome_user_data):
                self.log(f"   🌐 Launching real Chrome browser...")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self.chrome_user_data,
                    channel="chrome",
                    headless=headless,
                    args=[
                        f"--profile-directory={self.chrome_profile}",
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--start-maximized",
                        "--no-restore-session-state",
                        "--disable-session-crashed-bubble",
                        "--disable-infobars"
                    ],
                    viewport=None,
                )
            else:
                self.log("   ⚠️ Chrome not found, using Chromium...")
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                stealth = Stealth()
                await stealth.apply_stealth_async(context)
            
            page = context.pages[0] if context.pages else await context.new_page()
            
            stats = {"found": 0, "sent": 0, "skipped": 0, "failed": 0, "job_title": "N/A"}
            
            try:
                # 1. Check login status
                self.log(f"🔐 Checking login status...")
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                if "login" in page.url or "authwall" in page.url:
                    self.log("   Session expired. Please log in manually...")
                    for _ in range(60):
                        await asyncio.sleep(1)
                        if "feed" in page.url or "mynetwork" in page.url:
                            break
                    if "login" in page.url:
                        self.log("   ❌ Login timeout.")
                        stats["status"] = "login_failed"
                        return stats
                
                self.log("✅ Logged in successfully")

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
                await context.close()

    async def run_post_job(self, headless=False, company_config=None):
        """
        Smart free job posting with title rotation.
        - Tries each job title from the company's list
        - Detects if LinkedIn requires promotion/payment
        - Skips to next title if current one isn't free
        - Keeps trying until a free job is posted
        """
        self.log(f"📝 Starting Smart Job Post for {self.email}...")
        
        if not company_config:
            company_config = {
                "name": "Unknown",
                "job_titles": ["Architect", "Interior Designer", "Senior Architect"],
                "default_location": "Delhi, India",
                "workplace_type": "On-site"
            }
        
        job_titles = company_config.get("job_titles", ["Architect"])
        location = company_config.get("default_location", "Delhi, India")
        company_name = company_config.get("name", "Company")
        
        self.log(f"   Company: {company_name}")
        self.log(f"   Location: {location}")
        self.log(f"   Available Titles: {len(job_titles)}")
        
        # Load used titles tracking
        used_titles_file = self.session_dir / f"{self.email.replace('@','_').replace('.','_')}_used_titles.json"
        used_titles = {}
        if used_titles_file.exists():
            try:
                with open(used_titles_file, "r") as f:
                    used_titles = json.load(f)
            except: pass
        
        async with async_playwright() as p:
            # Use real Chrome with persistent profile
            if self.chrome_exe and os.path.exists(self.chrome_user_data):
                self.log(f"   🌐 Launching real Chrome browser...")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self.chrome_user_data,
                    channel="chrome",
                    headless=headless,
                    args=[
                        f"--profile-directory={self.chrome_profile}",
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--start-maximized",
                        "--no-restore-session-state",
                        "--disable-session-crashed-bubble",
                        "--disable-infobars"
                    ],
                    viewport=None,
                )
            else:
                self.log("   ⚠️ Chrome not found, using Chromium...")
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
                stealth = Stealth()
                await stealth.apply_stealth_async(context)
            
            page = context.pages[0] if context.pages else await context.new_page()
            stats = {"status": "pending", "tried_titles": [], "posted_title": None, "requires_promotion": []}
            
            try:
                # 1. Check login
                self.log(f"🔐 Checking login status...")
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                if "login" in page.url or "authwall" in page.url:
                    self.log("   Session expired. Please log in manually...")
                    for _ in range(60):
                        await asyncio.sleep(1)
                        if "feed" in page.url or "mynetwork" in page.url:
                            break
                    if "login" in page.url:
                        stats["status"] = "login_failed"
                        return stats
                
                self.log("✅ Logged in successfully")

                # 2. Try each job title until one can be posted for free
                for title_idx, job_title in enumerate(job_titles):
                    self.log(f"\n{'='*50}")
                    self.log(f"🔄 Trying Title [{title_idx + 1}/{len(job_titles)}]: {job_title}")
                    self.log(f"{'='*50}")
                    
                    stats["tried_titles"].append(job_title)
                    
                    # Check if title was used recently (within 7 days)
                    if job_title in used_titles:
                        from datetime import datetime
                        last_used = datetime.fromisoformat(used_titles[job_title])
                        days_ago = (datetime.now() - last_used).days
                        if days_ago < 7:
                            self.log(f"   ⏭️ Skipping - Used {days_ago} days ago (need 7+ days)")
                            continue
                    
                    # Navigate to job posting page
                    self.log("   📋 Navigating to job posting...")
                    await page.goto("https://www.linkedin.com/job-posting/", wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    
                    # Alternative URLs to try
                    if "job-posting" not in page.url:
                        alternative_urls = [
                            "https://www.linkedin.com/talent/post-a-job",
                            "https://www.linkedin.com/jobs/post/"
                        ]
                        for alt_url in alternative_urls:
                            try:
                                await page.goto(alt_url, wait_until="domcontentloaded")
                                await asyncio.sleep(2)
                                break
                            except: continue
                    
                    # Click "Post a free job" button if present
                    free_job_clicked = await self.fast_click(page, [
                        'button:has-text("Post a free job")',
                        'a:has-text("Post a free job")',
                        'button:has-text("Post job")',
                        'button:has-text("Get started")',
                        '[data-test-id="post-job-button"]'
                    ], timeout=5000)
                    
                    if free_job_clicked:
                        await asyncio.sleep(2)
                    
                    # Fill in job title
                    self.log(f"   ✏️ Entering job title: {job_title}")
                    title_input_selectors = [
                        'input[name="job-title"]',
                        'input[placeholder*="title"]',
                        'input[aria-label*="Job title"]',
                        '#job-title-input',
                        'input[id*="job-title"]',
                        '.jobs-form__job-title input',
                        'input.ember-text-field'
                    ]
                    
                    title_filled = False
                    for selector in title_input_selectors:
                        try:
                            title_input = await page.wait_for_selector(selector, timeout=3000)
                            if title_input:
                                await title_input.click()
                                await title_input.fill("")
                                await page.keyboard.type(job_title, delay=50)
                                await asyncio.sleep(1)
                                # Press Tab or click away to trigger validation
                                await page.keyboard.press("Tab")
                                await asyncio.sleep(2)
                                title_filled = True
                                self.log(f"   ✅ Title entered")
                                break
                        except:
                            continue
                    
                    if not title_filled:
                        self.log(f"   ❌ Could not fill job title field")
                        try:
                            await page.screenshot(path=str(self.base_dir / f"debug_post_job_{title_idx}.png"))
                        except: pass
                        continue
                    
                    # Fill in company name (if field exists and is empty)
                    try:
                        company_input = await page.query_selector('input[name="company"], input[aria-label*="Company"]')
                        if company_input:
                            current_value = await company_input.get_attribute("value")
                            if not current_value:
                                await company_input.fill(company_name)
                                self.log(f"   ✏️ Entered company: {company_name}")
                    except: pass
                    
                    # Fill location
                    self.log(f"   ✏️ Entering location: {location}")
                    try:
                        location_selectors = [
                            'input[name="location"]',
                            'input[placeholder*="location"]',
                            'input[aria-label*="Location"]',
                            'input[aria-label*="City"]'
                        ]
                        for loc_sel in location_selectors:
                            loc_input = await page.query_selector(loc_sel)
                            if loc_input:
                                await loc_input.click()
                                await loc_input.fill("")
                                await page.keyboard.type(location, delay=30)
                                await asyncio.sleep(1)
                                # Select from dropdown if appears
                                dropdown_option = await page.query_selector('.basic-typeahead__selectable:first-child, [role="option"]:first-child')
                                if dropdown_option:
                                    await dropdown_option.click()
                                self.log(f"   ✅ Location set")
                                break
                    except: pass
                    
                    # Click Continue/Next to proceed
                    self.log("   ⏭️ Proceeding to next step...")
                    await self.fast_click(page, [
                        'button:has-text("Continue")',
                        'button:has-text("Next")',
                        'button[type="submit"]',
                        '.artdeco-button--primary'
                    ], timeout=5000)
                    await asyncio.sleep(3)
                    
                    # Check if this title requires promotion (not free)
                    page_content = await page.content()
                    page_text = await page.inner_text('body')
                    
                    requires_payment = any(keyword in page_text.lower() for keyword in [
                        "promote your job",
                        "boost your job",
                        "reach more candidates",
                        "sponsored",
                        "per day",
                        "per click",
                        "budget",
                        "payment",
                        "add budget",
                        "promote",
                        "$ per"
                    ])
                    
                    # Also check for explicit free option
                    has_free_option = any(keyword in page_text.lower() for keyword in [
                        "post for free",
                        "free job post",
                        "basic (free)",
                        "free listing",
                        "no promotion"
                    ])
                    
                    if requires_payment and not has_free_option:
                        self.log(f"   💰 This title requires PROMOTION - not free!")
                        stats["requires_promotion"].append(job_title)
                        
                        # Try to find and click "Skip" or "No thanks" for promotion
                        skip_clicked = await self.fast_click(page, [
                            'button:has-text("Skip")',
                            'button:has-text("No thanks")',
                            'button:has-text("Post for free")',
                            'a:has-text("Skip")',
                            'button:has-text("Continue without")'
                        ], timeout=3000)
                        
                        if not skip_clicked:
                            self.log(f"   ⏭️ Skipping to next title...")
                            continue
                    
                    # If we have a free option, select it
                    if has_free_option:
                        self.log("   🆓 Free option available!")
                        await self.fast_click(page, [
                            'button:has-text("Post for free")',
                            'input[value="free"]',
                            'label:has-text("Free")',
                            'div:has-text("Basic (Free)")'
                        ], timeout=3000)
                        await asyncio.sleep(1)
                    
                    # Continue through the form (click Continue/Next multiple times)
                    for step in range(8): # Increased steps for more complex forms
                        await asyncio.sleep(2)
                        
                        # 1. Check for success
                        current_text = await page.inner_text('body')
                        if any(success in current_text.lower() for success in [
                            "job posted", "successfully posted", "your job is live",
                            "job is now live", "congratulations"
                        ]):
                            self.log(f"   🎉 JOB POSTED SUCCESSFULLY: {job_title}")
                            stats["status"] = "success"
                            stats["posted_title"] = job_title
                            
                            # Track used title
                            used_titles[job_title] = datetime.now().isoformat()
                            with open(used_titles_file, "w") as f:
                                json.dump(used_titles, f, indent=2)
                            
                            await self.save_cookies(context)
                            return stats
                        
                        # 2. Look for "Draft with AI" or autogenerate buttons
                        ai_selectors = [
                            'button:has-text("Draft with AI")',
                            'button:has-text("Use AI")',
                            'button:has-text("Rewrite with AI")',
                            'button[aria-label*="AI"]',
                            '.jobs-description-v2__ai-button'
                        ]
                        
                        for ai_sel in ai_selectors:
                            try:
                                ai_btn = await page.query_selector(ai_sel)
                                if ai_btn and await ai_btn.is_visible():
                                    self.log("   🤖 Found 'Draft with AI' button. Clicking...")
                                    await ai_btn.click()
                                    await asyncio.sleep(3) # Wait for AI generation
                                    # After AI drafting, we might need to click "Save" or "Done"
                                    break
                            except: pass

                        # 3. Look for "Description" field if we're stuck
                        try:
                            desc_box = await page.query_selector('.ql-editor, [role="textbox"][aria-label*="description"]')
                            if desc_box and not (await desc_box.inner_text()).strip():
                                self.log("   📝 Description box empty. Attempting to trigger AI if button not found...")
                                # Sometimes clicking the box triggers an AI prompt
                                await desc_box.click()
                                await asyncio.sleep(1)
                        except: pass

                        # 4. Try to continue to next step
                        clicked = await self.fast_click(page, [
                            'button:has-text("Continue")',
                            'button:has-text("Next")',
                            'button:has-text("Post job")',
                            'button:has-text("Publish")',
                            'button:has-text("Post for free")',
                            'button:has-text("Done")',
                            'button[type="submit"]:not([disabled])',
                            '.artdeco-button--primary:not([disabled])'
                        ], timeout=3000)
                        
                        if not clicked:
                            # Try keyboard Enter as fallback
                            await page.keyboard.press("Enter")
                            await asyncio.sleep(2)
                    
                    # Final check for success after form completion
                    await asyncio.sleep(2)
                    final_text = await page.inner_text('body')
                    if any(success in final_text.lower() for success in [
                        "job posted", "successfully posted", "your job is live"
                    ]):
                        self.log(f"   🎉 JOB POSTED SUCCESSFULLY: {job_title}")
                        stats["status"] = "success"
                        stats["posted_title"] = job_title
                        
                        # Track used title
                        used_titles[job_title] = datetime.now().isoformat()
                        with open(used_titles_file, "w") as f:
                            json.dump(used_titles, f, indent=2)
                        
                        await self.save_cookies(context)
                        return stats
                    
                    self.log(f"   ⚠️ Could not confirm job posting for: {job_title}")
                    try:
                        await page.screenshot(path=str(self.base_dir / f"debug_post_job_{title_idx}.png"))
                    except: pass
                
                # If we tried all titles and none worked
                if stats["status"] == "pending":
                    self.log("\n❌ COULD NOT POST ANY FREE JOB")
                    self.log(f"   Tried {len(stats['tried_titles'])} titles")
                    self.log(f"   Titles requiring promotion: {stats['requires_promotion']}")
                    stats["status"] = "no_free_slot"
                    
                    try:
                        await page.screenshot(path=str(self.base_dir / "debug_post_job_final.png"))
                        self.log("   Debug screenshot saved")
                    except: pass
                
                await self.save_cookies(context)
                return stats
                
            except Exception as e:
                self.log(f"💥 Error: {str(e)}")
                stats["status"] = "error"
                stats["error"] = str(e)
                return stats
            finally:
                await context.close()


    async def run_close_jobs(self, headless=False):
        """Scan for paused/expired job posts and close them."""
        self.log(f"🛑 Starting Audit & Close Jobs for {self.email}...")
        self.log(f"   Using Chrome profile: {self.chrome_profile}")
        
        async with async_playwright() as p:
            # Use real Chrome with persistent profile to avoid detection
            if self.chrome_exe and os.path.exists(self.chrome_user_data):
                self.log(f"   🌐 Launching real Chrome browser...")
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self.chrome_user_data,
                    channel="chrome",  # Use installed Chrome
                    headless=headless,
                    args=[
                        f"--profile-directory={self.chrome_profile}",
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--start-maximized",
                        "--no-restore-session-state",
                        "--disable-session-crashed-bubble",
                        "--disable-infobars"
                    ],
                    viewport=None,
                )
            else:
                # Fallback to Chromium if Chrome not found
                self.log("   ⚠️ Chrome not found, using Chromium (may be detected)...")
                browser = await p.chromium.launch(headless=headless)
                context = await browser.new_context(
                    viewport={"width": 1440, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                stealth = Stealth()
                await stealth.apply_stealth_async(context)
            
            page = context.pages[0] if context.pages else await context.new_page()
            stats = {"status": "pending", "scanned": 0, "closed": 0, "paused": 0, "active": 0, "jobs": []}
            
            try:
                # 1. Check if already logged in (real Chrome profile should have session)
                self.log(f"🔐 Checking login status...")
                await page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                await asyncio.sleep(3)
                
                # If we're on the feed, we're logged in. If redirected to login, handle it.
                if "login" in page.url or "authwall" in page.url:
                    self.log("   Session expired. Please log in manually in the browser window...")
                    # Wait for user to log in manually (up to 60 seconds)
                    for _ in range(60):
                        await asyncio.sleep(1)
                        if "feed" in page.url or "mynetwork" in page.url:
                            break
                    if "login" in page.url:
                        self.log("   ❌ Login timeout. Please run in visible mode and log in.")
                        stats["status"] = "login_failed"
                        return stats
                
                self.log("✅ Logged in successfully")

                # 2. Navigate to Job Management page
                self.log("📋 Navigating to job management...")
                
                # Extended list of job management URLs
                job_urls = [
                    "https://www.linkedin.com/my-items/posted-jobs/",
                    "https://www.linkedin.com/jobs/manage/",
                    "https://www.linkedin.com/hiring/jobs/",
                    "https://www.linkedin.com/talent/hire/jobs",
                    "https://www.linkedin.com/job-posting/manage/",
                    "https://www.linkedin.com/jobs/view/manage/"
                ]
                
                jobs_found = False
                for url in job_urls:
                    try:
                        await page.goto(url, wait_until="domcontentloaded")
                        await asyncio.sleep(4)
                        self.log(f"   Trying URL: {url}")
                        
                        # Check if page has job listings
                        content = await page.content()
                        item_count = len(await page.query_selector_all('.artdeco-list__item, .job-card-container, [data-view-name="job-card"]'))
                        
                        if item_count > 0:
                            jobs_found = True
                            self.log(f"   ✅ Found {item_count} jobs at: {url}")
                            break
                        elif any(kw in content.lower() for kw in ["paused", "closed", "active", "job post"]):
                            jobs_found = True
                            self.log(f"   ✅ Found jobs page (by text) at: {url}")
                            break
                    except Exception as e:
                        self.log(f"   ❌ Failed to load {url}: {str(e)[:50]}")
                        continue
                
                # Fallback: Try navigating via Jobs menu
                if not jobs_found:
                    self.log("   Trying menu navigation...")
                    try:
                        await page.goto("https://www.linkedin.com/jobs/", wait_until="domcontentloaded")
                        await asyncio.sleep(2)
                        
                        # Look for "Manage job posts" link
                        manage_selectors = [
                            'a:has-text("Manage job posts")',
                            'a:has-text("My jobs")',
                            'a:has-text("Posted jobs")',
                            '[href*="posted-jobs"]',
                            '[href*="/jobs/manage/"]'
                        ]
                        for m_sel in manage_selectors:
                            m_btn = await page.query_selector(m_sel)
                            if m_btn:
                                await m_btn.click()
                                await asyncio.sleep(3)
                                jobs_found = True
                                self.log(f"   ✅ Navigated to management via: {m_sel}")
                                break
                    except: pass
                
                if not jobs_found:
                    self.log("⚠️ Could not find job management page. Saving debug screenshot...")
                    try:
                        await page.screenshot(path=str(self.base_dir / "debug_close_jobs.png"))
                        self.log("   Debug screenshot saved.")
                    except: pass
                
                # 3. Find and inventory jobs
                self.log("🔍 Scanning job posts...")
                
                # Try to dismiss any modals
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)
                
                # Auto-scroll to load all jobs
                self.log("   📜 Scrolling to load more jobs...")
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                
                job_selectors = [
                    '.artdeco-list__item',
                    '.job-card-container',
                    '[data-view-name="job-card"]',
                    '.jobs-manage-card',
                    '.reusable-search__result-container',
                    'li[class*="artdeco-list__item"]',
                    'div[class*="job-card"]',
                    '.artdeco-card'
                ]
                
                job_items = []
                for selector in job_selectors:
                    try:
                        items = await page.query_selector_all(selector)
                        if items and len(items) > 0:
                            # Filter out small/empty items
                            valid_items = []
                            for itm in items:
                                text = (await itm.inner_text()).strip()
                                if len(text) > 10:
                                    valid_items.append(itm)
                            
                            if valid_items:
                                job_items = valid_items
                                self.log(f"   Searching with: {selector}")
                                self.log(f"   ✅ Found {len(valid_items)} potential job items")
                                break
                    except: continue

                if not job_items:
                    self.log("   Trying extremely broad search (any list item)...")
                    try:
                        items = await page.query_selector_all('li')
                        valid_items = []
                        for itm in items:
                            text = (await itm.inner_text()).strip()
                            if len(text) > 20 and any(kw in text.lower() for kw in ['architect', 'designer', 'job', 'posted', 'applicant', 'manage']):
                                valid_items.append(itm)
                        if valid_items:
                            job_items = valid_items
                            self.log(f"   ✅ Found {len(job_items)} items via word matching")
                    except: pass

                if not job_items:
                    self.log("   🏁 No jobs detected using any selector.")
                    stats["status"] = "no_jobs"
                    return stats
                
                stats["scanned"] = len(job_items)
                
                # 4. Analyze each job
                items_to_process = job_items if job_items else (all_links if 'all_links' in dir() else [])
                
                for i, item in enumerate(items_to_process):
                    try:
                        # Get job details
                        text = await item.inner_text()
                        lines = text.strip().split('\n')
                        job_title = lines[0] if lines else f"Job {i+1}"
                        
                        job_info = {
                            "title": job_title[:50],
                            "status": "unknown",
                            "action": "none"
                        }
                        
                        self.log(f"--- Job {i+1}: {job_title[:40]}... ---")
                        
                        # Check for indicators of paused/dead/expired jobs
                        text_lower = text.lower()
                        is_paused = 'paused' in text_lower
                        is_expired = any(keyword in text_lower for keyword in [
                            'expired', 'closed', 'inactive', 'no longer accepting', 'draft'
                        ])
                        is_zero_applicants = '0 applicant' in text_lower
                        is_old = any(keyword in text_lower for keyword in [
                            '30+ days', '60+ days', '90+ days', 'month ago', 'months ago'
                        ])
                        
                        should_close = is_paused or is_expired
                        
                        if is_paused:
                            job_info["status"] = "paused"
                            stats["paused"] += 1
                            self.log(f"   ⏸️ Status: PAUSED - Will close")
                        elif is_expired:
                            job_info["status"] = "expired"
                            self.log(f"   ⚠️ Status: EXPIRED - Will close")
                        elif is_old:
                            job_info["status"] = "old"
                            self.log(f"   ⏰ Status: OLD (30+ days)")
                            should_close = True  # Also close old jobs
                        else:
                            job_info["status"] = "active"
                            stats["active"] += 1
                            self.log(f"   ✅ Status: ACTIVE")
                        
                        stats["jobs"].append(job_info)
                        
                        # DEBUG: Save HTML of the job item to understand why it is/isnt paused
                        try:
                            item_html = await item.inner_html()
                            debug_filename = self.base_dir / f"debug_job_{i}_{'paused' if is_paused else 'active'}.html"
                            with open(debug_filename, "w", encoding="utf-8") as f:
                                f.write(f"<!-- Status: {job_info['status']} -->\n")
                                f.write(f"<!-- Valid Text: {text} -->\n")
                                f.write(item_html)
                        except: pass

                        
                        # If paused, expired, or old - try to close it
                        if should_close:
                            self.log(f"   🔧 Attempting to close job (opening detail view)...")
                            
                            # Click on the job TITLE or card to open the Detail Page
                            # User says: "click on the posted job open it and then itll take u to the job post"
                            navigated_to_detail = False
                            try:
                                # Try clicking the title specifically if possible, else the card
                                title_link = await item.query_selector('a[href*="/hiring/jobs/"], .job-card-list__title, strong, .artdeco-entity-lockup__title')
                                if title_link:
                                    await title_link.click()
                                else:
                                    await item.click()
                                    
                                await page.wait_for_load_state("domcontentloaded")
                                await asyncio.sleep(3)
                                
                                # Check if we are on a detail page
                                if "/hiring/jobs/" in page.url or "/jobs/view/" in page.url:
                                    self.log(f"   ✅ Opened job detail page: {page.url}")
                                    navigated_to_detail = True
                                else:
                                    self.log(f"   ⚠️ Did not navigate to detail page. Current URL: {page.url}")
                                    # Might have opened in a side-panel? Check for close button anyway
                            except Exception as e:
                                self.log(f"   ❌ Could not navigate to job detail: {e}")
                                continue
                            
                            if navigated_to_detail:
                                # Look for "Close job" button on the detail page
                                # User screenshot shows a clear "Close job" button next to "View applicants"
                                close_btn_selectors = [
                                    'button:has-text("Close job")',
                                    'a:has-text("Close job")',
                                    '[aria-label="Close job"]',
                                    '.jobs-details-top-card__close-btn', # Hypothetical
                                    'main button:has-text("Close")'
                                ]
                                
                                close_btn = None
                                for sel in close_btn_selectors:
                                    try:
                                        btn = await page.wait_for_selector(sel, state="visible", timeout=2000)
                                        if btn:
                                            # Double check it's not "Close" as in "Dismiss modal"
                                            txt = await btn.inner_text()
                                            if "close job" in txt.lower():
                                                close_btn = btn
                                                break
                                    except: continue
                                
                                if close_btn:
                                    self.log(f"   ✅ Found 'Close job' button. Clicking...")
                                    await close_btn.click()
                                    await asyncio.sleep(1)
                                    
                                    # Handle confirmation dialog
                                    confirm_selectors = [
                                        'button.artdeco-modal__confirm-btn',
                                        'button.artdeco-button--primary:has-text("Close")',
                                        'button:has-text("Confirm")',
                                        'button:has-text("Yes")',
                                        'button:has-text("Close job")' # Sometimes the confirm button has same text
                                    ]
                                    
                                    confirmed = False
                                    for c_sel in confirm_selectors:
                                        try:
                                            c_btn = await page.wait_for_selector(c_sel, state="visible", timeout=2000)
                                            if c_btn:
                                                await c_btn.click()
                                                self.log(f"   ✅ Confirmed close.")
                                                confirmed = True
                                                stats["closed"] += 1
                                                job_info["action"] = "closed"
                                                break
                                        except: continue
                                    
                                    if not confirmed:
                                        self.log("   ⚠️ Clicked Close but found no confirmation dialog (might have auto-closed).")
                                        stats["closed"] += 1 # Assume success if no dialog blocked it?
                                        
                                else:
                                    # Fallback: Maybe it's in the "..." menu on the detail page
                                    self.log("   ⚠️ 'Close job' button not found directly. Checking '...' menu...")
                                    try:
                                        more_btn = await page.wait_for_selector('button[aria-label*="More actions"], button[aria-label*="Options"]', timeout=2000)
                                        if more_btn:
                                            await more_btn.click()
                                            await asyncio.sleep(1)
                                            close_opt = await page.wait_for_selector('div:has-text("Close job"), span:has-text("Close job")', timeout=2000)
                                            if close_opt:
                                                await close_opt.click()
                                                # Confirm logic again...
                                                await asyncio.sleep(1)
                                                confirm_btn = await page.wait_for_selector('button.artdeco-button--primary', timeout=2000)
                                                if confirm_btn: 
                                                    await confirm_btn.click()
                                                    self.log("   ✅ Closed via menu.")
                                                    stats["closed"] += 1
                                                    job_info["action"] = "closed"
                                    except:
                                        self.log("   ❌ Could not close job on detail page.")

                            # Go back to list for next item
                            self.log("   🔙 Returning to job list...")
                            await page.goto(job_urls[0], wait_until="domcontentloaded")
                            await asyncio.sleep(3)
                            
                            # Must refresh the items list since DOM is gone
                            # We break the inner loop to re-fetch items in the outer loop or restart search
                            # But since we are iterating a stored list of handles that might be stale...
                            # Actually, `items_to_process` loops over handles. If we navigate away, these handles become invalid (detached).
                            # So we MUST break the loop and restart scanning (or re-acquire list).
                            # Since we just closed one, the list changed.
                            self.log("   🔄 Reloading job list...")
                            break # Break the item loop to re-scan from scratch
                            
                    except Exception as e:
                        self.log(f"   ❌ Error processing job {i+1}: {str(e)[:50]}")
                        continue
                
                # Summary
                self.log("=" * 50)
                self.log("📊 AUDIT & CLOSE SUMMARY")
                self.log("=" * 50)
                self.log(f"   Total Scanned: {stats['scanned']}")
                self.log(f"   Active Jobs:   {stats['active']}")
                self.log(f"   Paused Jobs:   {stats['paused']}")
                self.log(f"   Jobs Closed:   {stats['closed']}")
                
                if stats['closed'] == 0 and (stats['paused'] > 0 or any(j['status'] in ['paused', 'expired'] for j in stats['jobs'])):
                    self.log("⚠️ Some jobs could not be closed automatically.")
                    self.log("   Please try running in visible mode to see the process.")
                    try:
                        await page.screenshot(path=str(self.base_dir / "debug_close_jobs.png"))
                        self.log("   Debug screenshot saved.")
                    except: pass
                
                stats["status"] = "success"
                await self.save_cookies(context)
                return stats
                
            except Exception as e:
                self.log(f"💥 Error: {str(e)}")
                stats["status"] = "error"
                stats["error"] = str(e)
                return stats
            finally:
                await context.close()

    async def perform_manual_login(self, page):
        await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
        await page.fill('input[name="session_key"]', self.email)
        await page.fill('input[name="session_password"]', self.password)
        await page.click('button[type="submit"]')
        
        for _ in range(60):
            await asyncio.sleep(1)
            if "login" not in page.url: return True
        return False
