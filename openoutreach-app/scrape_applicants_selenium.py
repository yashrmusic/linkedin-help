from linkedin_scraper import Job, Company, actions
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import csv

EMAIL = "jobs@deco-arte.in"
PASSWORD = "yash Yr19950903!"
OUTPUT_CSV = "assets/inputs/urls.csv"

# Set up Chrome options for Selenium
chrome_options = Options()
chrome_options.add_argument("--start-maximized")

# You may need to specify the path to chromedriver if not in PATH
# driver = webdriver.Chrome(executable_path="/path/to/chromedriver", options=chrome_options)
driver = webdriver.Chrome(options=chrome_options)

actions.login(driver, EMAIL, PASSWORD)  # if 2FA, complete it manually

input("\nAfter you are logged in and see your LinkedIn feed, manually navigate to your posted jobs page and open your job post. Then press Enter here to continue scraping applicants...\n")

# Scrape all applicant profile links from the job post page
def scrape_applicant_links(driver):
    links = set()
    # This selector may need to be updated based on LinkedIn's UI
    applicant_elems = driver.find_elements("xpath", '//a[contains(@href, "/in/")]')
    for elem in applicant_elems:
        url = elem.get_attribute("href")
        if url and "/in/" in url:
            links.add(url)
    return list(links)

applicant_links = scrape_applicant_links(driver)

with open(OUTPUT_CSV, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["linkedin_url"])
    for url in applicant_links:
        writer.writerow([url])

print(f"Saved {len(applicant_links)} applicant URLs to {OUTPUT_CSV}")

driver.quit()
