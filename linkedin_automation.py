"""
LinkedIn Automation Script
- Login to LinkedIn
- Navigate to job posts
- Send "hi" to all applicants
- Save cookies for session persistence
"""

import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD")
COOKIES_FILE = Path(__file__).parent / "cookies.json"


async def save_cookies(context: BrowserContext):
    """Save browser cookies to a file for session persistence."""
    cookies = await context.cookies()
    with open(COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)
    print(f"✅ Cookies saved to {COOKIES_FILE}")


async def load_cookies(context: BrowserContext) -> bool:
    """Load cookies from file if they exist."""
    if COOKIES_FILE.exists():
        try:
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"✅ Cookies loaded from {COOKIES_FILE}")
            return True
        except Exception as e:
            print(f"⚠️ Failed to load cookies: {e}")
            return False
    return False


async def login_to_linkedin(page: Page) -> bool:
    """Login to LinkedIn with credentials."""
    print("🔐 Logging in to LinkedIn...")
    
    await page.goto("https://www.linkedin.com/login")
    await page.wait_for_load_state("networkidle")
    
    # Check if already logged in
    if "feed" in page.url or "mynetwork" in page.url:
        print("✅ Already logged in!")
        return True
    
    # Fill in credentials
    await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
    await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
    
    # Click login button
    await page.click('button[type="submit"]')
    
    # Wait for navigation
    try:
        await page.wait_for_url("**/feed/**", timeout=30000)
        print("✅ Login successful!")
        return True
    except Exception:
        # Check for security verification
        current_url = page.url
        if "checkpoint" in current_url or "challenge" in current_url:
            print("⚠️ Security verification required. Please complete it manually...")
            print("Waiting 60 seconds for manual verification...")
            await asyncio.sleep(60)
            if "feed" in page.url:
                print("✅ Verification completed!")
                return True
        print(f"❌ Login might have failed. Current URL: {current_url}")
        return False


async def navigate_to_job_posts(page: Page):
    """Navigate to the job posting/hiring page."""
    print("📋 Navigating to job posts...")
    
    # Navigate to hiring/talent solutions
    await page.goto("https://www.linkedin.com/hiring/")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)
    
    print(f"📍 Current URL: {page.url}")


async def get_job_applicants_and_message(page: Page):
    """Find job posts and send messages to applicants."""
    print("🔍 Looking for job posts with applicants...")
    
    # Navigate to jobs page
    await page.goto("https://www.linkedin.com/jobs/")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)
    
    # Try to find "My Jobs" or "Posted Jobs" link
    try:
        # Look for the "My jobs" or "Manage job posts" section
        my_jobs_selectors = [
            'a[href*="/my-items/posted-jobs"]',
            'a:has-text("My jobs")',
            'a:has-text("Posted jobs")',
            '[data-control-name="posted_jobs"]',
            'a[href*="hiring"]',
        ]
        
        for selector in my_jobs_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    await element.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)
                    print(f"✅ Clicked on: {selector}")
                    break
            except Exception:
                continue
        
        print(f"📍 Current URL after navigation: {page.url}")
        
    except Exception as e:
        print(f"⚠️ Could not find job posts section: {e}")
    
    # Now try to access the free job posting applicants
    # Navigate directly to posted jobs
    await page.goto("https://www.linkedin.com/my-items/posted-jobs/")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)
    
    print(f"📍 Posted jobs URL: {page.url}")
    
    # Look for job cards with applicants
    job_cards = await page.query_selector_all('.job-card-container, .jobs-job-board-list__item, [data-job-id]')
    print(f"📊 Found {len(job_cards)} job cards")
    
    if len(job_cards) == 0:
        # Try alternative approach - click on management section
        print("🔄 Trying alternative navigation to hiring dashboard...")
        await page.goto("https://www.linkedin.com/talent/jobs")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        print(f"📍 Talent jobs URL: {page.url}")


async def send_message_to_applicant(page: Page, applicant_name: str):
    """Send a message to a specific applicant."""
    message = "Hi"
    
    try:
        # Look for message button
        message_btn = await page.query_selector('button:has-text("Message"), [data-control-name="message"]')
        if message_btn:
            await message_btn.click()
            await asyncio.sleep(2)
            
            # Type the message
            message_box = await page.query_selector('.msg-form__contenteditable, [role="textbox"], textarea')
            if message_box:
                await message_box.fill(message)
                await asyncio.sleep(1)
                
                # Send the message
                send_btn = await page.query_selector('button:has-text("Send"), [type="submit"]')
                if send_btn:
                    await send_btn.click()
                    print(f"✅ Sent 'Hi' to {applicant_name}")
                    await asyncio.sleep(2)
                    return True
    except Exception as e:
        print(f"❌ Failed to message {applicant_name}: {e}")
    
    return False


async def process_applicants(page: Page):
    """Process all applicants from job posts and send messages."""
    print("👥 Processing applicants...")
    
    # Get all applicant elements
    applicant_selectors = [
        '.hiring-applicants__list-item',
        '.applicant-card',
        '[data-applicant-id]',
        '.candidate-card',
        '.job-candidate-card',
    ]
    
    applicants = []
    for selector in applicant_selectors:
        applicants = await page.query_selector_all(selector)
        if len(applicants) > 0:
            print(f"📊 Found {len(applicants)} applicants with selector: {selector}")
            break
    
    if len(applicants) == 0:
        print("⚠️ No applicants found. Let's try to access them through the UI...")
        
        # Take a screenshot for debugging
        screenshot_path = Path(__file__).parent / "current_page.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"📸 Screenshot saved to {screenshot_path}")
        
        # Print page content for debugging
        content = await page.content()
        print(f"📄 Page title: {await page.title()}")
        return
    
    # Process each applicant
    sent_count = 0
    for i, applicant in enumerate(applicants):
        try:
            # Get applicant name
            name_element = await applicant.query_selector('span, .name, [data-test-name]')
            name = await name_element.inner_text() if name_element else f"Applicant {i+1}"
            
            # Click on the applicant
            await applicant.click()
            await asyncio.sleep(2)
            
            # Send message
            if await send_message_to_applicant(page, name):
                sent_count += 1
            
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"⚠️ Error processing applicant {i+1}: {e}")
    
    print(f"📊 Sent messages to {sent_count} applicants")


async def interactive_mode(page: Page):
    """
    Interactive mode - keeps browser open for manual navigation.
    Prompts user before proceeding with each step.
    """
    print("\n" + "="*60)
    print("🎮 INTERACTIVE MODE")
    print("="*60)
    print("The browser is now open. You can:")
    print("1. Navigate manually to your job posts")
    print("2. View applicants")
    print("3. The script will help you message them")
    print("\nPress Enter when you're on the page with applicants...")
    
    input()
    
    # Try to process applicants from current page
    await process_applicants(page)
    
    print("\n✅ Processing complete. Press Enter to save cookies and exit...")
    input()


async def main():
    """Main automation function."""
    print("🚀 LinkedIn Automation Starting...")
    print(f"📧 Email: {LINKEDIN_EMAIL}")
    
    async with async_playwright() as p:
        # Launch browser (not headless so you can see + interact if needed)
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=100,  # Slow down for visibility
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # Try to load existing cookies
        cookies_loaded = await load_cookies(context)
        
        if cookies_loaded:
            # Verify session is still valid
            await page.goto("https://www.linkedin.com/feed/")
            await page.wait_for_load_state("networkidle")
            
            if "login" in page.url:
                print("⚠️ Session expired, need to login again...")
                cookies_loaded = False
        
        if not cookies_loaded:
            # Login with credentials
            login_success = await login_to_linkedin(page)
            if login_success:
                await save_cookies(context)
            else:
                print("❌ Login failed. Please check your credentials.")
                await browser.close()
                return
        
        # Navigate to job posts
        await navigate_to_job_posts(page)
        
        # Try automatic processing first
        await get_job_applicants_and_message(page)
        
        # Enter interactive mode for manual assistance
        await interactive_mode(page)
        
        # Save cookies before closing
        await save_cookies(context)
        
        print("👋 Automation complete. Closing browser...")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
