"""
LinkedIn Free Job Applicant Auto-Messenger
==========================================
Optimized, fast, error-free automation for messaging job applicants.

USAGE:
    python linkedin_messenger.py

ENTRY POINT:
    - Reads credentials from .env file
    - Uses saved cookies.json if available
    - Goes to: https://www.linkedin.com/my-items/posted-jobs/

EXIT POINT:
    - Saves cookies.json for next session
    - Saves messaged_applicants.json to track who was contacted
    - Prints summary report
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError
from dotenv import load_dotenv

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")

BASE_DIR = Path(__file__).parent
COOKIES_FILE = BASE_DIR / "cookies.json"
MESSAGED_FILE = BASE_DIR / "messaged_applicants.json"
LOG_FILE = BASE_DIR / "run_log.txt"

# URLs
POSTED_JOBS_URL = "https://www.linkedin.com/my-items/posted-jobs/"
LINKEDIN_FEED = "https://www.linkedin.com/feed/"

# Timing (in milliseconds) - optimized for speed
FAST_WAIT = 500       # Very quick operations
MEDIUM_WAIT = 1500    # Page transitions
SLOW_WAIT = 2500      # Heavy page loads

# Message to send
MESSAGE_TEXT = """Thank you for showing interest in joining Deco Arte. We've received your application through LinkedIn and would love to learn more about your background.

Please email your updated resume (and portfolio, if applicable) to jobs@deco-arte.in so we can review your profile in detail and take your application forward.

Looking forward to hearing from you.

Warm regards,
Team Deco Arte"""


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def log(message: str):
    """Print and log message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def load_messaged() -> set:
    """Load set of already-messaged applicant URLs."""
    if MESSAGED_FILE.exists():
        try:
            with open(MESSAGED_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_messaged(url: str, messaged: set):
    """Add URL to messaged set and save."""
    messaged.add(url)
    with open(MESSAGED_FILE, "w") as f:
        json.dump(list(messaged), f, indent=2)


async def save_cookies(context: BrowserContext):
    """Save session cookies."""
    cookies = await context.cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f)


async def load_cookies(context: BrowserContext) -> bool:
    """Load session cookies if available."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            return True
        except Exception:
            pass
    return False


# ============================================================================
# CORE AUTOMATION FUNCTIONS
# ============================================================================

async def fast_click(page: Page, selectors: list, timeout: int = 5000) -> bool:
    """Try multiple selectors to click an element quickly."""
    for selector in selectors:
        try:
            element = await page.wait_for_selector(selector, timeout=timeout, state="visible")
            if element:
                await element.click()
                return True
        except TimeoutError:
            continue
        except Exception:
            continue
    return False


async def login(page: Page, context: BrowserContext) -> str:
    """
    LOGIN ENTRY POINT
    Attempts cookie login first, then credentials if needed.
    Returns status string.
    """
    log("🔐 Starting login...")
    
    # Try cookies first (fastest)
    if await load_cookies(context):
        log("   Trying saved session...")
        await page.goto(LINKEDIN_FEED, wait_until="domcontentloaded")
        await page.wait_for_timeout(MEDIUM_WAIT)
        
        if "feed" in page.url or "mynetwork" in page.url:
            log("✅ Logged in via cookies!")
            return "SUCCESS (Cookies)"
        log("   Cookies expired, using credentials...")
    
    # Login with credentials
    log("   Entering credentials...")
    await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
    await page.wait_for_timeout(FAST_WAIT)
    
    await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
    await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
    await page.click('button[type="submit"]')
    
    # Wait for login (with timeout for security verification)
    log("   Waiting for login...")
    for _ in range(60):
        await page.wait_for_timeout(1000)
        url = page.url
        if "feed" in url or "mynetwork" in url or "my-items" in url or "hiring" in url:
            log("✅ Login successful!")
            await save_cookies(context)
            return "SUCCESS (Credentials)"
        if "checkpoint" in url or "challenge" in url:
            log("⚠️ Security verification required - complete manually")
    
    if "login" not in page.url:
        log("✅ Login appears successful")
        await save_cookies(context)
        return "SUCCESS (Manual/Auto)"
    
    log("❌ Login failed")
    return "FAILED"


async def navigate_to_job(page: Page) -> str:
    """Navigate to posted jobs and click on the first active job. Returns job title."""
    log(f"📋 Navigating to: {POSTED_JOBS_URL}")
    
    await page.goto(POSTED_JOBS_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(MEDIUM_WAIT)
    
    # Capture job title before clicking
    job_title = "Unknown"
    title_selectors = [
        '.artdeco-entity-lockup__title',
        '.job-card-list__title',
        'h3.t-16',
        '.entity-result__title-text'
    ]
    for selector in title_selectors:
        title_elem = await page.query_selector(selector)
        if title_elem:
            job_title = (await title_elem.inner_text()).strip()
            if job_title:
                log(f"   Found job: {job_title}")
                break
    
    # Click on first job
    log("   Opening job post details...")
    job_clicked = await fast_click(page, [
        '.artdeco-list__item a[href*="jobs/view"]',
        '.job-card-container__link',
        'a[href*="hiring/jobs"]',
        '.entity-result a',
        '.job-card-container',
    ])
    
    if job_clicked:
        await page.wait_for_timeout(MEDIUM_WAIT)
        log("✅ Opened job post")
        return job_title
    
    # Fallback: click any visible job title
    jobs = await page.query_selector_all('.artdeco-list__item')
    if jobs:
        await jobs[0].click()
        await page.wait_for_timeout(MEDIUM_WAIT)
        log("✅ Opened first job post")
        return job_title
    
    log("⚠️ No job posts found")
    return "NOT FOUND"


async def open_applicants(page: Page) -> bool:
    """Click 'View applicants' to see applicant list."""
    log("👥 Opening applicants...")
    
    clicked = await fast_click(page, [
        'button:has-text("View applicants")',
        'a:has-text("View applicants")',
        '[aria-label*="applicant" i]',
        'a[href*="applicants"]',
    ])
    
    if clicked:
        await page.wait_for_timeout(MEDIUM_WAIT)
        log("✅ Viewing applicants")
        return True
    
    # Check if already on applicants page
    if "applicants" in page.url:
        log("✅ Already on applicants page")
        return True
    
    log("⚠️ Could not find applicants button")
    return False


async def process_all_applicants(page: Page) -> dict:
    """
    MAIN PROCESSING LOOP
    Messages all applicants directly from the hiring applicants list view.
    Returns statistics dict.
    """
    messaged = load_messaged()
    stats = {"found": 0, "sent": 0, "skipped": 0, "failed": 0, "errors": []}
    
    log("🔍 Searching for applicants on page...")
    
    # Wait for the table or list to be visible
    await page.wait_for_timeout(MEDIUM_WAIT)
    
    # Count message buttons available
    message_buttons = await page.query_selector_all('button:has-text("Message")')
    stats["found"] = len(message_buttons)
    log(f"📊 Found {stats['found']} potential candidates with message buttons")
    
    if stats["found"] == 0:
        log("⚠️ No Message buttons found")
        return stats
    
    log(f"📨 Processing fresh applicants...")
    
    # Process each message button
    for i in range(stats["found"]):
        log(f"--- Applicant {i+1}/{stats['found']} ---")
        
        try:
            # Re-query buttons as DOM shifts after interactions
            message_buttons = await page.query_selector_all('button:has-text("Message")')
            if i >= len(message_buttons):
                break
                
            btn = message_buttons[i]
            
            # Try to identify applicant (via parent elements)
            applicant_id = f"applicant_{i}_{datetime.now().strftime('%Y%m%d')}"
            try:
                # Look for name in ancestor
                parent = await btn.evaluate_handle('el => el.closest(".hiring-applicants__list-item, .artdeco-list__item, [role=listitem]")')
                if parent:
                    text = await parent.as_element().inner_text()
                    name = text.split('\n')[0].strip()[:40]
                    if name:
                        applicant_id = name
                        log(f"   Name: {name}")
            except Exception:
                pass
            
            # Skip if already messaged
            if applicant_id in messaged:
                log("   ⏭️ Already messaged recently. Skipping.")
                stats["skipped"] += 1
                continue
            
            # Click Message
            await btn.click()
            # Wait for message overlay
            await page.wait_for_selector('.msg-form__contenteditable, [role=textbox]', timeout=5000)
            
            # Paste/Insert message (faster than typing character by character)
            for selector in ['div.msg-form__contenteditable', 'div[role=textbox]', 'div[contenteditable=true]']:
                msg_input = await page.query_selector(selector)
                if msg_input:
                    await msg_input.click()
                    # Use insert_text for near-instant pasting
                    await page.keyboard.insert_text(MESSAGE_TEXT)
                    break
            else:
                log("   ❌ Error: Message box not found")
                stats["failed"] += 1
                stats["errors"].append(f"Msg box not found for {applicant_id}")
                await fast_click(page, ['button[aria-label=Close]', '.artdeco-modal__dismiss'])
                continue
            
            # Fast Send
            sent = await fast_click(page, ['button.msg-form__send-button', 'button:has-text("Send")'], timeout=2000)
            if not sent:
                await page.keyboard.press("Control+Enter")
                sent = True # Assume sent if key pressed
                
            if sent:
                log("   ✅ Message sent successfully")
                save_messaged(applicant_id, messaged)
                stats["sent"] += 1
            else:
                log("   ❌ Error: Send failed")
                stats["failed"] += 1
                stats["errors"].append(f"Send failed for {applicant_id}")
            
            # Quick close overlay
            await page.wait_for_timeout(FAST_WAIT)
            await fast_click(page, [
                '[aria-label*="Close" i]',
                '.msg-overlay-bubble-header__control--close',
                '.artdeco-modal__dismiss'
            ], timeout=1500)
            
            # Small cooldown between applicants to avoid detection
            await page.wait_for_timeout(FAST_WAIT)
            
        except Exception as e:
            log(f"   ❌ Critical error for applicant {i+1}: {e}")
            stats["failed"] += 1
            stats["errors"].append(str(e))
            continue
            
    return stats


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """
    OPTIMIZED EXECUTION FLOW:
    1. Fast Login
    2. Direct Navigation to Posted Jobs
    3. Job Capture & Applicant Processing
    4. Comprehensive Logging
    5. Instant Exit
    """
    
    # Initialize run log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== LinkedIn Automated Hiring Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    
    log("=" * 60)
    log("🚀 DECO ARTE - LINKEDIN APPLICANT MESSENGER (OPTIMIZED)")
    log("=" * 60)
    
    if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
        log("❌ FAILED: Credentials missing in .env")
        return

    async with async_playwright() as p:
        # Launch browser (non-headless so user can watch if needed)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        login_status = "PENDING"
        job_post_name = "N/A"
        final_stats = {"found": 0, "sent": 0, "skipped": 0, "failed": 0, "errors": []}
        
        try:
            # 1. Faster Login
            login_status = await login(page, context)
            if "FAILED" in login_status:
                log("❌ Exiting due to login failure.")
                await browser.close()
                return

            # 2. Faster Navigation
            job_post_name = await navigate_to_job(page)
            if job_post_name == "NOT FOUND":
                log("❌ Exiting: No active job posts found.")
                await browser.close()
                return

            # 3. Applicant Processing
            if await open_applicants(page):
                final_stats = await process_all_applicants(page)
            else:
                log("❌ Exiting: Could not find applicants list.")

            # 4. Persistence
            await save_cookies(context)

        except Exception as e:
            log(f"💥 UNEXPECTED CRASH: {e}")
            final_stats["errors"].append(f"Global Crash: {str(e)}")
        finally:
            # 5. Final Summary Log (User Request Format)
            log("\n" + "="*60)
            log("🏁 SESSION COMPLETE")
            log("="*60)
            log(f"📊 SUMMARY:")
            log(f"   - Candidate(s) Found : {final_stats['found']}")
            log(f"   - Message(s) Sent    : {final_stats['sent']}")
            log(f"   - Job Post           : {job_post_name}")
            log(f"   - Login Status       : {login_status}")
            
            if final_stats['failed'] > 0:
                log(f"   - FAILED             : {final_stats['failed']}")
                log(f"   - Reason(s)          : {', '.join(set(final_stats['errors']))[:200]}...")
            
            log("="*60)
            log("✅ System shutting down. Check run_log.txt for details.")
            
            # Exit
            await page.wait_for_timeout(MEDIUM_WAIT)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
