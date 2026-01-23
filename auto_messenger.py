"""
LinkedIn Free Job Post - FULLY AUTOMATED Applicant Messenger
No user input required - runs completely automatically
"""

import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL") 
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
COOKIES_FILE = Path(__file__).parent / "cookies.json"
MESSAGED_FILE = Path(__file__).parent / "messaged_applicants.json"

# Target URL
POSTED_JOBS_URL = "https://www.linkedin.com/my-items/posted-jobs/"


def load_messaged_applicants() -> set:
    if MESSAGED_FILE.exists():
        try:
            with open(MESSAGED_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_messaged_applicant(applicant_id: str, messaged: set):
    messaged.add(applicant_id)
    with open(MESSAGED_FILE, "w") as f:
        json.dump(list(messaged), f, indent=2)


async def save_cookies(context: BrowserContext):
    cookies = await context.cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    print("✅ Cookies saved!")


async def load_cookies(context: BrowserContext) -> bool:
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            return True
        except Exception as e:
            print(f"⚠️ Cookie load error: {e}")
    return False


async def login(page: Page, context: BrowserContext) -> bool:
    """Login to LinkedIn - fully automated."""
    # Try cookies first
    if await load_cookies(context):
        print("🔄 Trying saved cookies...")
        try:
            await page.goto("https://www.linkedin.com/feed/", timeout=60000, wait_until="domcontentloaded")
            await asyncio.sleep(3)
            
            if "login" not in page.url and "signup" not in page.url:
                print("✅ Logged in via cookies!")
                return True
        except Exception as e:
            print(f"⚠️ Cookie session check failed: {e}")
    
    # Login with credentials
    print("🔐 Logging in with credentials...")
    try:
        await page.goto("https://www.linkedin.com/login", timeout=60000)
        await asyncio.sleep(2)
        
        await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
        await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
        await page.click('button[type="submit"]')
        
        print("⏳ Waiting for login...")
        
        # Wait for successful login
        for i in range(90):
            await asyncio.sleep(1)
            current_url = page.url
            if "feed" in current_url or "mynetwork" in current_url or "my-items" in current_url:
                print("✅ Login successful!")
                await save_cookies(context)
                return True
            if "checkpoint" in current_url or "challenge" in current_url:
                print(f"⚠️ Security verification required - waiting... ({i}s)")
            if i % 20 == 0 and i > 0:
                print(f"   Still waiting... ({i}s)")
        
        # Check if we got through anyway
        if "login" not in page.url:
            print("✅ Appears to be logged in")
            await save_cookies(context)
            return True
            
    except Exception as e:
        print(f"❌ Login error: {e}")
    
    return False


async def click_element_safe(page: Page, selectors: list, description: str = "") -> bool:
    """Try multiple selectors to click an element."""
    for selector in selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                await element.click()
                await asyncio.sleep(2)
                print(f"   ✅ Clicked: {description or selector}")
                return True
        except Exception:
            continue
    return False


async def go_to_posted_jobs(page: Page) -> bool:
    """Navigate to posted jobs page."""
    print(f"\n📋 Going to: {POSTED_JOBS_URL}")
    try:
        await page.goto(POSTED_JOBS_URL, timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        print(f"📍 Current URL: {page.url}")
        return True
    except Exception as e:
        print(f"❌ Navigation error: {e}")
        return False


async def find_and_click_job(page: Page) -> bool:
    """Find the free job post and click on it."""
    print("\n🔍 Looking for job posts...")
    await asyncio.sleep(2)
    
    # Try to find job items/cards
    job_selectors = [
        '.artdeco-list__item a',
        '.job-card-container a',
        'a[href*="jobs/view"]',
        '.entity-result a',
        'a[href*="/jobs/"]',
    ]
    
    for selector in job_selectors:
        try:
            jobs = await page.query_selector_all(selector)
            if jobs:
                print(f"📊 Found {len(jobs)} job elements")
                for job in jobs:
                    href = await job.get_attribute("href")
                    if href and "jobs" in href:
                        await job.click()
                        await asyncio.sleep(3)
                        print("✅ Clicked on job post")
                        return True
        except Exception:
            continue
    
    # Try clicking on list items directly
    list_items = await page.query_selector_all('.artdeco-list__item, li[class*="job"]')
    if list_items:
        print(f"📊 Found {len(list_items)} list items, clicking first one...")
        await list_items[0].click()
        await asyncio.sleep(3)
        return True
    
    print("⚠️ Could not find job post")
    return False


async def find_applicants_section(page: Page) -> bool:
    """Navigate to applicants section."""
    print("\n👥 Looking for applicants...")
    await asyncio.sleep(2)
    
    # Look for applicants link/button
    selectors = [
        'a[href*="applicant"]',
        'button:has-text("View applicant")',
        'a:has-text("applicant")',
        'span:has-text("applicant")',
        '[data-control-name*="applicant"]',
    ]
    
    if await click_element_safe(page, selectors, "applicants section"):
        await asyncio.sleep(3)
        return True
    
    # Try looking in tabs
    tabs = await page.query_selector_all('[role="tab"], .artdeco-tab')
    for tab in tabs:
        try:
            text = await tab.inner_text()
            if "applicant" in text.lower():
                await tab.click()
                await asyncio.sleep(3)
                print("✅ Clicked applicants tab")
                return True
        except Exception:
            continue
    
    # Check current page content
    content = await page.content()
    if "applicant" in content.lower():
        print("✅ Already on applicants page")
        return True
    
    print("⚠️ Could not find applicants section")
    return False


async def send_hello(page: Page, profile_url: str, messaged: set) -> bool:
    """Send 'Hello' message to current profile."""
    if profile_url in messaged:
        print("   ⏭️ Already messaged")
        return False
    
    try:
        # Click message button
        msg_clicked = await click_element_safe(page, [
            'button:has-text("Message")',
            'a:has-text("Message")',
            '[aria-label*="message" i]',
            'button.pvs-profile-actions__action:has-text("Message")',
        ], "Message button")
        
        if not msg_clicked:
            print("   ⚠️ No Message button")
            return False
        
        await asyncio.sleep(3)  # Wait longer for dialog
        
        # Find message input - try multiple approaches
        input_selectors = [
            'div.msg-form__contenteditable',
            'div[role="textbox"]',
            'div[contenteditable="true"]',
            '.msg-form__message-texteditor div[contenteditable]',
            'p.msg-form__placeholder',
        ]
        
        msg_typed = False
        for selector in input_selectors:
            try:
                msg_input = await page.query_selector(selector)
                if msg_input:
                    await msg_input.click()
                    await asyncio.sleep(0.5)
                    await page.keyboard.type("Hello")
                    await asyncio.sleep(1)
                    msg_typed = True
                    print("   ✅ Typed 'Hello'")
                    break
            except Exception:
                continue
        
        if not msg_typed:
            print("   ⚠️ Could not type message")
            return False
        
        # Try to send - multiple methods
        sent = False
        
        # Method 1: Click send button
        send_selectors = [
            'button.msg-form__send-button',
            'button:has-text("Send")',
            'button[type="submit"]',
            'button.msg-form__send-btn',
        ]
        
        for selector in send_selectors:
            try:
                send_btn = await page.query_selector(selector)
                if send_btn:
                    # Check if it's enabled
                    is_disabled = await send_btn.get_attribute("disabled")
                    if not is_disabled:
                        await send_btn.click()
                        await asyncio.sleep(2)
                        sent = True
                        print("   ✅ Clicked Send button")
                        break
            except Exception:
                continue
        
        # Method 2: Use keyboard shortcut (Ctrl+Enter or Enter)
        if not sent:
            try:
                await page.keyboard.press("Enter")
                await asyncio.sleep(2)
                sent = True
                print("   ✅ Pressed Enter to send")
            except Exception:
                pass
        
        if sent:
            save_messaged_applicant(profile_url, messaged)
            print("   ✅ Sent 'Hello'!")
            
            # Try to close message popup
            await asyncio.sleep(1)
            await click_element_safe(page, [
                'button[aria-label*="Close"]',
                '.msg-overlay-bubble-header__control--close',
                'button.artdeco-modal__dismiss',
            ], "close popup")
            
            return True
        
        print("   ⚠️ Could not send message")
        return False
        
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return False


async def process_applicants(page: Page) -> int:
    """Find and message all applicants."""
    messaged = load_messaged_applicants()
    sent_count = 0
    
    print("\n🔍 Finding applicant profiles...")
    
    # Get profile links
    profile_links = await page.query_selector_all('a[href*="/in/"]')
    unique_profiles = []
    seen_hrefs = set()
    
    for link in profile_links:
        try:
            href = await link.get_attribute("href")
            if href and "/in/" in href and href not in seen_hrefs:
                seen_hrefs.add(href)
                unique_profiles.append(href)
        except Exception:
            continue
    
    if not unique_profiles:
        print("⚠️ No applicant profiles found")
        # Take debug screenshot
        await page.screenshot(path=str(Path(__file__).parent / "debug.png"), full_page=True)
        print("📸 Debug screenshot saved")
        return 0
    
    print(f"📊 Found {len(unique_profiles)} unique profiles")
    
    for i, profile_url in enumerate(unique_profiles):
        print(f"\n[{i+1}/{len(unique_profiles)}] Opening: {profile_url[:60]}...")
        
        try:
            # Navigate to profile
            full_url = profile_url if profile_url.startswith("http") else f"https://www.linkedin.com{profile_url}"
            await page.goto(full_url, timeout=30000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Send message
            if await send_hello(page, full_url, messaged):
                sent_count += 1
            
            # Small delay between profiles
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"   ⚠️ Error: {e}")
            continue
    
    return sent_count


async def main():
    """Main entry point - fully automated."""
    print("="*60)
    print("🚀 LinkedIn Applicant Messenger - FULLY AUTOMATED")
    print("="*60)
    print(f"📧 Email: {LINKEDIN_EMAIL}")
    print(f"🎯 Target: {POSTED_JOBS_URL}")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100,
        )
        
        context = await browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        try:
            # Step 1: Login
            if not await login(page, context):
                print("\n❌ Login failed. Please check credentials.")
                await asyncio.sleep(10)
                await browser.close()
                return
            
            # Step 2: Go to posted jobs
            if not await go_to_posted_jobs(page):
                print("❌ Could not navigate to posted jobs")
                await browser.close()
                return
            
            # Step 3: Click on the free job
            if not await find_and_click_job(page):
                print("⚠️ Waiting 10 seconds for page to load...")
                await asyncio.sleep(10)
                await find_and_click_job(page)
            
            # Step 4: Find applicants section
            await find_applicants_section(page)
            
            # Step 5: Process all applicants
            sent_count = await process_applicants(page)
            
            # Save cookies
            await save_cookies(context)
            
            print("\n" + "="*60)
            print(f"✅ DONE! Sent 'Hello' to {sent_count} applicants")
            print("="*60)
            
            # Keep browser open for 10 seconds so user can see results
            print("\nBrowser will close in 10 seconds...")
            await asyncio.sleep(10)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await asyncio.sleep(5)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
