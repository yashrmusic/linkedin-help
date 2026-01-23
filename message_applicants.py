"""
LinkedIn Job Applicant Messenger
Specifically designed for free job posts - sends "Hi" to all applicants
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


def load_messaged_applicants() -> set:
    """Load list of already messaged applicants."""
    if MESSAGED_FILE.exists():
        with open(MESSAGED_FILE, "r") as f:
            return set(json.load(f))
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
        except Exception:
            return False
    return False


async def wait_and_click(page: Page, selector: str, timeout: int = 10000):
    """Wait for element and click it."""
    try:
        element = await page.wait_for_selector(selector, timeout=timeout)
        if element:
            await element.click()
            return True
    except Exception:
        return False
    return False


async def login(page: Page, context: BrowserContext) -> bool:
    """Handle LinkedIn login."""
    # Try loading cookies first
    if await load_cookies(context):
        await page.goto("https://www.linkedin.com/feed/")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        if "feed" in page.url:
            print("✅ Logged in via saved cookies!")
            return True
    
    # Manual login
    print("🔐 Logging in with credentials...")
    await page.goto("https://www.linkedin.com/login")
    await page.wait_for_load_state("networkidle")
    
    await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
    await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
    await page.click('button[type="submit"]')
    
    # Wait for redirect or verification
    print("⏳ Waiting for login... (Complete any verification if prompted)")
    
    max_wait = 120  # 2 minutes for manual verification if needed
    for i in range(max_wait):
        await asyncio.sleep(1)
        if "feed" in page.url or "mynetwork" in page.url:
            print("✅ Login successful!")
            await save_cookies(context)
            return True
        if i % 10 == 0:
            print(f"   Waiting... ({i}s)")
    
    print("❌ Login timeout")
    return False


async def go_to_my_profile(page: Page):
    """Navigate to user's own profile."""
    print("👤 Going to your profile...")
    
    # Click on profile picture/Me link
    try:
        me_button = await page.query_selector('.global-nav__me, [data-control-name="nav.settings_signout"]')
        if me_button:
            await me_button.click()
            await asyncio.sleep(1)
    except Exception:
        pass
    
    # Try direct navigation
    await page.goto("https://www.linkedin.com/in/me/")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)
    
    print(f"📍 Profile URL: {page.url}")
    return True


async def go_to_job_posting_page(page: Page):
    """Navigate to the job posting management page."""
    print("📋 Going to job posting page...")
    
    # Different possible URLs for job posting management
    possible_urls = [
        "https://www.linkedin.com/talent/post-a-job",
        "https://www.linkedin.com/jobs/post",
        "https://www.linkedin.com/hiring/jobs",
        "https://www.linkedin.com/my-items/posted-jobs/",
        "https://www.linkedin.com/job-posting/",
    ]
    
    for url in possible_urls:
        print(f"   Trying: {url}")
        await page.goto(url)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)
        
        # Check if we found the right page
        title = await page.title()
        print(f"   Page title: {title}")
        
        if "posting" in page.url.lower() or "hiring" in page.url.lower() or "posted" in page.url.lower():
            print(f"✅ Found job posting page: {page.url}")
            return True
    
    return False


async def find_and_message_applicants(page: Page):
    """Find applicants and send messages."""
    messaged = load_messaged_applicants()
    
    print("🔍 Looking for applicants...")
    
    # Take screenshot for debugging
    screenshot_path = Path(__file__).parent / "job_page.png"
    await page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"📸 Screenshot saved: {screenshot_path}")
    
    # Look for any clickable applicant elements
    # LinkedIn's DOM structure varies, so we try multiple selectors
    applicant_selectors = [
        'a[href*="/in/"]',  # Profile links
        '.applicant-card',
        '.candidate-card', 
        '[data-applicant-urn]',
        '.hiring-applicant',
        '.job-candidate',
    ]
    
    for selector in applicant_selectors:
        elements = await page.query_selector_all(selector)
        if elements:
            print(f"📊 Found {len(elements)} elements with selector: {selector}")
    
    # Get all profile links on the page
    profile_links = await page.query_selector_all('a[href*="/in/"]')
    print(f"📊 Found {len(profile_links)} profile links")
    
    sent_count = 0
    
    for link in profile_links:
        try:
            href = await link.get_attribute("href")
            if not href or href in messaged:
                continue
            
            # Get the person's name
            name = await link.inner_text()
            name = name.strip()
            
            if not name or len(name) < 2:
                continue
            
            print(f"👤 Found: {name} ({href})")
            
            # Open profile in new context to message
            await link.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            
            # Look for message button
            message_clicked = await click_message_button(page)
            
            if message_clicked:
                # Type and send message
                await send_hi_message(page)
                save_messaged_applicant(href, messaged)
                sent_count += 1
                print(f"✅ Sent 'Hi' to {name}")
            
            # Go back
            await page.go_back()
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"⚠️ Error: {e}")
            continue
    
    print(f"\n📊 Summary: Sent messages to {sent_count} applicants")


async def click_message_button(page: Page) -> bool:
    """Click the message button on a profile."""
    message_selectors = [
        'button:has-text("Message")',
        '[data-control-name="message"]',
        '.pv-top-card-v2-ctas button:has-text("Message")',
        'button.message-anywhere-button',
    ]
    
    for selector in message_selectors:
        if await wait_and_click(page, selector, timeout=3000):
            await asyncio.sleep(2)
            return True
    
    return False


async def send_hi_message(page: Page) -> bool:
    """Type 'Hi' and send the message."""
    try:
        # Find message input
        message_box_selectors = [
            '.msg-form__contenteditable',
            '[role="textbox"]',
            'div[contenteditable="true"]',
            'textarea',
        ]
        
        for selector in message_box_selectors:
            try:
                msg_box = await page.wait_for_selector(selector, timeout=5000)
                if msg_box:
                    await msg_box.click()
                    await page.keyboard.type("Hi")
                    await asyncio.sleep(1)
                    
                    # Find and click send button
                    send_selectors = [
                        'button:has-text("Send")',
                        'button[type="submit"]',
                        '.msg-form__send-button',
                    ]
                    
                    for send_sel in send_selectors:
                        if await wait_and_click(page, send_sel, timeout=3000):
                            await asyncio.sleep(2)
                            return True
                    break
            except Exception:
                continue
                
    except Exception as e:
        print(f"⚠️ Send error: {e}")
    
    return False


async def manual_workflow(page: Page, context: BrowserContext):
    """
    Semi-manual workflow with guidance.
    """
    print("\n" + "="*60)
    print("📋 SEMI-MANUAL WORKFLOW")
    print("="*60)
    print("""
The browser is now open. Here's what you need to do:

1. Navigate to your FREE job post
2. Click on "View applicants" or similar
3. Press ENTER here when you're viewing the applicants list

The script will then attempt to message each applicant.
""")
    
    input("Press ENTER when ready to start messaging applicants...")
    
    # Try to find and message applicants on current page
    await find_and_message_applicants(page)
    
    # Option for multiple job posts
    while True:
        response = input("\nDo you have another job post to process? (y/n): ")
        if response.lower() != 'y':
            break
        
        input("Navigate to the next job's applicants, then press ENTER...")
        await find_and_message_applicants(page)
    
    # Save cookies before exit
    await save_cookies(context)
    print("\n✅ All done! Cookies saved for next session.")


async def main():
    """Main entry point."""
    print("="*60)
    print("🚀 LinkedIn Job Applicant Messenger")
    print("="*60)
    print(f"Email: {LINKEDIN_EMAIL}")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=50,
        )
        
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # Login
        if not await login(page, context):
            print("❌ Failed to login. Exiting.")
            await browser.close()
            return
        
        # Go to profile
        await go_to_my_profile(page)
        
        # Try to find job posting page
        found_jobs = await go_to_job_posting_page(page)
        
        if not found_jobs:
            print("⚠️ Could not find job posting page automatically.")
        
        # Enter semi-manual workflow
        await manual_workflow(page, context)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
