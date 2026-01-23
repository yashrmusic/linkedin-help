import asyncio
from playwright.async_api import async_playwright
import csv


LINKEDIN_EMAIL = "jobs@deco-arte.in"
LINKEDIN_PASSWORD = "yash Yr19950903!"
POSTED_JOBS_URL = "https://www.linkedin.com/my-items/posted-jobs/"
OUTPUT_CSV = "assets/inputs/urls.csv"


async def scrape_applicant_urls():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Login

        await page.goto("https://www.linkedin.com/login")
        await page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
        await page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
        await page.click('button[type="submit"]')

        print("\nIf you see 2FA, captcha, or any manual login step, please complete it in the browser window.")

        input("\nPress Enter here after you are fully logged in.\nThen, in the browser, manually navigate to your posted jobs page (https://www.linkedin.com/my-items/posted-jobs/) and wait for it to load.\nWhen you see your job(s), press Enter again here to continue scraping applicants...\n")

        # Save cookies after manual login
        cookies = await context.storage_state(path="assets/cookies/manual_login_cookies.json")
        print("Cookies saved to assets/cookies/manual_login_cookies.json. Future runs can reuse this session.")

        # Click the first active job ad (assume only 1 active)
        job_cards = await page.query_selector_all('a[href*="/jobs/view/"]')
        if not job_cards:
            print("No active job ads found.")
            await browser.close()
            return
        await job_cards[0].click()
        await page.wait_for_load_state('networkidle')

        # Click on the applicants link/button
        applicants_btn = await page.query_selector('a:has-text("applicant")')
        if not applicants_btn:
            print("No applicants link found on job page.")
            await browser.close()
            return
        await applicants_btn.click()
        await page.wait_for_load_state('networkidle')

        # Scroll to load all applicants
        for _ in range(10):
            await page.mouse.wheel(0, 10000)
            await asyncio.sleep(1)

        # Extract applicant profile URLs
        applicant_links = await page.eval_on_selector_all(
            'a[href*="/in/"]', 'elements => elements.map(e => e.href)'
        )
        # Remove duplicates
        applicant_links = list(set(applicant_links))

        # Save to CSV
        with open(OUTPUT_CSV, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["linkedin_url"])
            for url in applicant_links:
                writer.writerow([url])
        print(f"Saved {len(applicant_links)} applicant URLs to {OUTPUT_CSV}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(scrape_applicant_urls())
