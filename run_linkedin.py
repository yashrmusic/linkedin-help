"""
LinkedIn Automation - Robust Version
Opens browser, logs in, and helps you message applicants
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
    return False


async def safe_goto(page: Page, url: str, timeout: int = 60000):
    """Navigate to URL with extended timeout and error handling."""
    try:
        await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        return True
    except Exception as e:
        print(f"⚠️ Navigation warning: {e}")
        await asyncio.sleep(3)
        return True  # Continue anyway


async def login_with_cookies(page: Page, context: BrowserContext) -> bool:
    """Try to login using saved cookies."""
    if not await load_cookies(context):
        return False
    
    print("🔄 Trying saved cookies...")
    await safe_goto(page, "https://www.linkedin.com/feed/")
    
    # Check if we're logged in
    current_url = page.url
    if "login" not in current_url and "signup" not in current_url:
        print("✅ Logged in via cookies!")
        return True
    
    return False


async def login_with_credentials(page: Page):
    """Login with email and password."""
    print("🔐 Logging in with credentials...")
    await safe_goto(page, "https://www.linkedin.com/login")
    
    try:
        # Wait for login form
        await page.wait_for_selector('input[name="session_key"]', timeout=10000)
        
        # Fill credentials
        await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
        await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
        
        # Click login
        await page.click('button[type="submit"]')
        
        print("⏳ Waiting for login to complete...")
        print("   (If verification is required, please complete it in the browser)")
        
        # Wait for redirect - give user time for verification
        for i in range(60):  # Wait up to 60 seconds
            await asyncio.sleep(1)
            current_url = page.url
            if "feed" in current_url or "mynetwork" in current_url or "jobs" in current_url:
                print("✅ Login successful!")
                return True
            if i % 10 == 0 and i > 0:
                print(f"   Still waiting... ({i}s)")
        
        # Check final state
        if "login" not in page.url:
            print("✅ Appears to be logged in")
            return True
            
    except Exception as e:
        print(f"⚠️ Login error: {e}")
    
    return False


async def navigate_to_hiring(page: Page):
    """Navigate to hiring/job posting pages."""
    print("\n📋 Navigating to hiring pages...")
    
    # First, try the main navigation links
    hiring_urls = [
        "https://www.linkedin.com/talent/post-a-job/context",
        "https://www.linkedin.com/hiring/jobs",
        "https://www.linkedin.com/my-items/posted-jobs",
        "https://www.linkedin.com/jobs/",
    ]
    
    for url in hiring_urls:
        print(f"   Trying: {url}")
        if await safe_goto(page, url):
            title = await page.title()
            print(f"   Page: {title}")
            await asyncio.sleep(2)
            
            # Check if this looks like a job management page
            content = await page.content()
            if "applicant" in content.lower() or "candidate" in content.lower() or "posted" in content.lower():
                print(f"✅ Found relevant page!")
                return True
    
    return False


async def send_message_to_current_profile(page: Page, messaged: set) -> bool:
    """Send 'Hi' message to the profile currently being viewed."""
    try:
        # Get current URL as identifier
        profile_url = page.url
        
        if profile_url in messaged:
            print("   Already messaged this person, skipping...")
            return False
        
        # Look for message button
        message_selectors = [
            'button:has-text("Message")',
            '[aria-label*="message"]',
            'button.artdeco-button--primary:has-text("Message")',
        ]
        
        for selector in message_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    await asyncio.sleep(2)
                    break
            except Exception:
                continue
        else:
            print("   ⚠️ Could not find Message button")
            return False
        
        # Wait for message dialog and type
        await asyncio.sleep(1)
        
        # Find message input
        input_selectors = [
            'div.msg-form__contenteditable',
            'div[contenteditable="true"]',
            'div[role="textbox"]',
        ]
        
        for selector in input_selectors:
            try:
                msg_input = await page.query_selector(selector)
                if msg_input:
                    await msg_input.click()
                    await page.keyboard.type("Hi")
                    await asyncio.sleep(1)
                    break
            except Exception:
                continue
        else:
            print("   ⚠️ Could not find message input")
            return False
        
        # Click send
        send_selectors = [
            'button:has-text("Send")',
            'button.msg-form__send-button',
        ]
        
        for selector in send_selectors:
            try:
                send_btn = await page.query_selector(selector)
                if send_btn:
                    await send_btn.click()
                    await asyncio.sleep(2)
                    save_messaged_applicant(profile_url, messaged)
                    print("   ✅ Message sent!")
                    return True
            except Exception:
                continue
        
        print("   ⚠️ Could not find Send button")
        return False
        
    except Exception as e:
        print(f"   ⚠️ Error sending message: {e}")
        return False


async def interactive_loop(page: Page, context: BrowserContext):
    """Interactive mode - user navigates, we help message."""
    messaged = load_messaged_applicants()
    sent_count = 0
    
    print("\n" + "="*60)
    print("🎮 INTERACTIVE MODE")
    print("="*60)
    print("""
The browser is open and you're logged in!

INSTRUCTIONS:
1. Navigate to your FREE job post in the browser
2. Find the "View applicants" or applicants list
3. Click on an applicant's profile
4. Come back here and type 'm' to send "Hi" message
5. Repeat for each applicant

COMMANDS:
  m  - Send "Hi" to current profile
  s  - Save cookies and continue
  q  - Save and quit
  
Navigate in the browser to any applicant profile, then use commands here.
""")
    
    while True:
        try:
            cmd = input("\nCommand (m=message, s=save, q=quit): ").strip().lower()
            
            if cmd == 'q':
                await save_cookies(context)
                print(f"\n📊 Session complete! Sent {sent_count} messages.")
                break
            
            elif cmd == 's':
                await save_cookies(context)
                print("✅ Cookies saved!")
                
            elif cmd == 'm':
                print(f"📍 Current URL: {page.url}")
                if await send_message_to_current_profile(page, messaged):
                    sent_count += 1
                    print(f"   Total messaged this session: {sent_count}")
                    
            else:
                print("Unknown command. Use m, s, or q")
                
        except KeyboardInterrupt:
            print("\n\nInterrupted. Saving cookies...")
            await save_cookies(context)
            break
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Main entry point."""
    print("="*60)
    print("🚀 LinkedIn Job Applicant Messenger")
    print("="*60)
    print(f"📧 Email: {LINKEDIN_EMAIL}")
    print()
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=50,
        )
        
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = await context.new_page()
        
        # Try cookie login first
        logged_in = await login_with_cookies(page, context)
        
        if not logged_in:
            logged_in = await login_with_credentials(page)
            if logged_in:
                await save_cookies(context)
        
        if not logged_in:
            print("\n❌ Could not log in. Please check credentials.")
            print("   Keeping browser open for manual login...")
            print("   Press Enter when logged in manually...")
            input()
            await save_cookies(context)
        
        # Try to navigate to hiring pages
        await navigate_to_hiring(page)
        
        # Enter interactive loop
        await interactive_loop(page, context)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
