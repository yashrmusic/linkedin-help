import asyncio
from linkedin_engine import LinkedInEngine
from pathlib import Path
import os

async def establish():
    base_dir = Path(__file__).parent
    
    accounts = [
        {"email": "mail@urbanmistrii.com", "pass": "Lolokok1"},
        {"email": "yashr.otp@gmail.com", "pass": "Lolokok1"}
    ]
    
    template = "Hello" # Placeholder
    
    for acc in accounts:
        print(f"\n--- Establishing session for {acc['email']} ---")
        engine = LinkedInEngine(acc['email'], acc['pass'], template, base_dir)
        # We run the invite applicants job but just far enough to log in
        # We'll use headless=False so if there's an OTP, the user can see it (if they were watching)
        # But here I'll just run the login part
        
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Use the engine's login logic
            status = await engine.perform_manual_login(page)
            if status:
                print(f"✅ Login successful for {acc['email']}")
                await engine.save_cookies(context)
            else:
                print(f"❌ Login failed for {acc['email']}")
            
            await browser.close()

if __name__ == "__main__":
    asyncio.run(establish())
