"""
LinkedIn Free Job Post - Applicant Messenger
Goes to posted jobs, opens the free job, messages all applicants "Hello"
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
    """Load list of already messaged applicants."""
    if MESSAGED_FILE.exists():
        try:
            with open(MESSAGED_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_messaged_applicant(applicant_id: str, messaged: set):
    """Save applicant to messaged list."""
    messaged.add(applicant_id)
    with open(MESSAGED_FILE, "w") as f:
        json.dump(list(messaged), f, indent=2)


async def save_cookies(context: BrowserContext):
    """Save cookies to file."""
    cookies = await context.cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    print("✅ Cookies saved!")


async def load_cookies(context: BrowserContext) -> bool:
    """Load cookies from file."""
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
    """Login to LinkedIn."""
    # Try cookies first
    if await load_cookies(context):
        print("🔄 Trying saved cookies...")
        await page.goto("https://www.linkedin.com/feed/", timeout=60000, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        if "login" not in page.url and "signup" not in page.url:
            print("✅ Logged in via cookies!")
            return True
    
    # Login with credentials
    print("🔐 Logging in with credentials...")
    await page.goto("https://www.linkedin.com/login", timeout=60000)
    await asyncio.sleep(2)
    
    await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
    await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
    await page.click('button[type="submit"]')
    
    print("⏳ Waiting for login... (complete any verification if prompted)")
    
    for i in range(90):  # Wait up to 90 seconds for verification
        await asyncio.sleep(1)
        if "feed" in page.url or "mynetwork" in page.url or "my-items" in page.url:
            print("✅ Login successful!")
            await save_cookies(context)
            return True
        if i % 15 == 0 and i > 0:
            print(f"   Waiting... ({i}s) - Complete verification if needed")
    
    if "login" not in page.url:
        await save_cookies(context)
        return True
    
    return False


async def go_to_posted_jobs(page: Page):
    """Navigate to posted jobs page."""
    print(f"\n📋 Going to: {POSTED_JOBS_URL}")
    await page.goto(POSTED_JOBS_URL, timeout=60000, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    print(f"📍 Current URL: {page.url}")


async def find_and_click_free_job(page: Page) -> bool:
    """Find the free job post and click on it."""
    print("\n🔍 Looking for free job post...")
    
    # Wait for the page to load
    await asyncio.sleep(2)
    
    # Look for job cards/items
    job_selectors = [
        '.artdeco-list__item',
        '.job-card-container',
        '[data-view-name="job-card"]',
        '.entity-result',
        'li.reusable-search__result-container',
    ]
    
    for selector in job_selectors:
        jobs = await page.query_selector_all(selector)
        if jobs:
            print(f"📊 Found {len(jobs)} job items with selector: {selector}")
            
            # Click on the first one (should be the free job)
            if len(jobs) > 0:
                await jobs[0].click()
                await asyncio.sleep(3)
                print("✅ Clicked on job post")
                return True
    
    # Alternative: look for any clickable job title link
    job_links = await page.query_selector_all('a[href*="jobs/view"]')
    if job_links:
        print(f"📊 Found {len(job_links)} job links")
        await job_links[0].click()
        await asyncio.sleep(3)
        return True
    
    # Try clicking on any visible job title
    titles = await page.query_selector_all('span.job-card-list__title, .entity-result__title-text')
    if titles:
        await titles[0].click()
        await asyncio.sleep(3)
        return True
    
    print("⚠️ Could not find job post automatically")
    return False


async def go_to_applicants(page: Page) -> bool:
    """Navigate to the applicants section of the job."""
    print("\n👥 Looking for applicants section...")
    
    # Look for "View applicants" or applicants tab/link
    applicant_selectors = [
        'a:has-text("applicant")',
        'button:has-text("applicant")',
        '[data-control-name="view_applicants"]',
        'a[href*="applicants"]',
        '.hiring-applicants-header',
        'span:has-text("applicants")',
    ]
    
    for selector in applicant_selectors:
        try:
            element = await page.query_selector(selector)
            if element:
                await element.click()
                await asyncio.sleep(3)
                print("✅ Navigated to applicants section")
                return True
        except Exception:
            continue
    
    # Check if we're already on applicants page
    content = await page.content()
    if "applicant" in content.lower():
        print("✅ Already viewing applicants")
        return True
    
    print("⚠️ Could not find applicants section")
    return False


async def get_applicant_profiles(page: Page) -> list:
    """Get all applicant profile links/elements."""
    print("\n🔍 Finding applicant profiles...")
    
    # Various selectors for applicant items
    selectors = [
        '.hiring-applicants__list-item',
        '.hiring-applicant-card',
        'a[href*="/in/"]',  # Profile links
        '.entity-result__item',
        '[data-view-name="profile-card"]',
    ]
    
    for selector in selectors:
        elements = await page.query_selector_all(selector)
        if elements:
            print(f"📊 Found {len(elements)} applicants with selector: {selector}")
            return elements
    
    return []


async def send_hello_to_profile(page: Page, messaged: set) -> bool:
    """Send 'Hello' message to current profile."""
    profile_url = page.url
    
    # Skip if already messaged
    if profile_url in messaged:
        print("   ⏭️ Already messaged, skipping...")
        return False
    
    try:
        # Find and click message button
        message_btn = None
        message_selectors = [
            'button:has-text("Message")',
            'a:has-text("Message")',
            '[aria-label*="Message"]',
            'button.artdeco-button--primary',
        ]
        
        for selector in message_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    text = await btn.inner_text()
                    if "message" in text.lower():
                        message_btn = btn
                        break
            except Exception:
                continue
        
        if not message_btn:
            print("   ⚠️ No Message button found")
            return False
        
        await message_btn.click()
        await asyncio.sleep(2)
        
        # Find message input and type
        input_selectors = [
            'div.msg-form__contenteditable',
            'div[role="textbox"]',
            'div[contenteditable="true"]',
        ]
        
        msg_input = None
        for selector in input_selectors:
            try:
                msg_input = await page.query_selector(selector)
                if msg_input:
                    break
            except Exception:
                continue
        
        if not msg_input:
            print("   ⚠️ No message input found")
            return False
        
        await msg_input.click()
        await asyncio.sleep(0.5)
        await page.keyboard.type("Hello")
        await asyncio.sleep(1)
        
        # Find and click send button
        send_selectors = [
            'button:has-text("Send")',
            'button.msg-form__send-button',
            'button[type="submit"]',
        ]
        
        for selector in send_selectors:
            try:
                send_btn = await page.query_selector(selector)
                if send_btn:
                    await send_btn.click()
                    await asyncio.sleep(2)
                    save_messaged_applicant(profile_url, messaged)
                    print("   ✅ Sent 'Hello'!")
                    
                    # Close the message dialog/popup if present
                    try:
                        close_btn = await page.query_selector('button[aria-label="Close"], button.msg-overlay-bubble-header__control--close')
                        if close_btn:
                            await close_btn.click()
                            await asyncio.sleep(0.5)
                    except Exception:
                        pass
                    
                    return True
            except Exception:
                continue
        
        print("   ⚠️ Could not send message")
        return False
        
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return False


async def process_all_applicants(page: Page):
    """Main loop to process all applicants."""
    messaged = load_messaged_applicants()
    sent_count = 0
    
    # Get all applicant elements
    applicants = await get_applicant_profiles(page)
    
    if not applicants:
        print("\n⚠️ No applicants found on this page.")
        print("   The page might have a different structure.")
        print("   Taking screenshot for debugging...")
        await page.screenshot(path=str(Path(__file__).parent / "debug_screenshot.png"), full_page=True)
        return 0
    
    print(f"\n🎯 Processing {len(applicants)} applicants...")
    
    for i, applicant in enumerate(applicants):
        try:
            print(f"\n[{i+1}/{len(applicants)}] Processing applicant...")
            
            # Try to get name or identifier
            try:
                name = await applicant.inner_text()
                name = name.split('\n')[0].strip()[:50]  # First line, truncated
                print(f"   Name: {name}")
            except Exception:
                name = f"Applicant {i+1}"
            
            # Get profile URL if it's a link
            try:
                href = await applicant.get_attribute("href")
                if href and "/in/" in href:
                    # Navigate to profile
                    if not href.startswith("http"):
                        href = "https://www.linkedin.com" + href
                    
                    await page.goto(href, timeout=30000, wait_until="domcontentloaded")
                    await asyncio.sleep(2)
                    
                    if await send_hello_to_profile(page, messaged):
                        sent_count += 1
                    
                    # Go back to applicants list
                    await page.go_back()
                    await asyncio.sleep(2)
                else:
                    # Click on the element instead
                    await applicant.click()
                    await asyncio.sleep(2)
                    
                    if await send_hello_to_profile(page, messaged):
                        sent_count += 1
                    
                    await page.go_back()
                    await asyncio.sleep(2)
                    
            except Exception as e:
                print(f"   ⚠️ Error navigating: {e}")
                continue
            
            # Re-fetch applicants after going back
            applicants = await get_applicant_profiles(page)
            if not applicants:
                print("   Lost applicant list, stopping...")
                break
                
        except Exception as e:
            print(f"   ⚠️ Error processing applicant {i+1}: {e}")
            continue
    
    print(f"\n📊 Summary: Sent 'Hello' to {sent_count} applicants")
    return sent_count


async def main():
    """Main entry point."""
    print("="*60)
    print("🚀 LinkedIn Free Job Post - Applicant Messenger")
    print("="*60)
    print(f"📧 Email: {LINKEDIN_EMAIL}")
    print(f"🎯 Target: {POSTED_JOBS_URL}")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100,  # Slow down so we can see what's happening
        )
        
        context = await browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # Step 1: Login
        if not await login(page, context):
            print("\n❌ Login failed.")
            input("Press Enter to close browser...")
            await browser.close()
            return
        
        # Step 2: Go to posted jobs
        await go_to_posted_jobs(page)
        
        # Step 3: Find and click the free job
        job_found = await find_and_click_free_job(page)
        if not job_found:
            print("\n⚠️ Could not find job automatically.")
            print("   Please click on your free job post in the browser...")
            input("   Press Enter when you've clicked on the job...")
        
        # Step 4: Go to applicants
        applicants_found = await go_to_applicants(page)
        if not applicants_found:
            print("\n⚠️ Could not find applicants section.")
            print("   Please navigate to the applicants in the browser...")
            input("   Press Enter when viewing applicants...")
        
        # Step 5: Process all applicants
        await process_all_applicants(page)
        
        # Save cookies
        await save_cookies(context)
        
        print("\n✅ Done! Cookies saved for next time.")
        input("Press Enter to close browser...")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
