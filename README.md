# Job Automation Hub 🚀

A powerful, AI-driven automation suite for managing recruitment across **LinkedIn, Internshala, and Naukri**. 
Designed for high-performance teams to automate mundane tasks like job posting, reposting, applicant outreach, and job closing.

## 🌟 Key Features

*   **Multi-Platform Support**: Automates LinkedIn, Internshala, and Naukri from a single dashboard.
*   **Smart Job Management**: 
    *   **Auto-Post**: Rotates through job titles to find free slots.
    *   **Auto-Close**: Detects paused/expired jobs and closes them to free up slots.
    *   **Maintenance Mode**: Keeps your job slots 100% active 24/7.
*   **AI-Powered Outreach**: Sends personalized messages to applicants automatically.
*   **Stealth Mode 🥷**: Uses real Chrome profiles and advanced stealth techniques to mimic human behavior and avoid detection.
*   **Beautiful UI**: A premium, "OLED Glass" dark-mode dashboard for monitoring and control.
*   **Mobile Ready**: Fully responsive design for managing your hiring from your phone.

## 🛠️ Tech Stack

*   **Backend**: Python, FastAPI
*   **Automation**: Playwright (Async), Playwright Stealth
*   **Frontend**: HTML5, Vanilla CSS (Glassmorphism), JavaScript
*   **Deployment**: Docker Ready, Supports Oracle Cloud / VPS

## 🚀 Getting Started

### Prerequisites

1.  Python 3.10+
2.  Google Chrome (for visible mode)
3.  `pip`

### Installation

1.  **Clone the repo**
    ```bash
    git clone https://github.com/yashrmusic/linkedin-help.git
    cd linkedin-help
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

3.  **Configure Accounts**
    Edit `accounts.yaml` with your platform credentials and job preferences.
    *   *Pro Tip: For LinkedIn, you can specify a `chrome_profile` to use your existing browser session!*

4.  **Run the Server**
    ```bash
    python app.py
    ```
    Access the dashboard at `http://localhost:8001`

## 🐳 Docker Deployment

To run on a VPS (like Oracle Cloud):

```bash
docker-compose up --build -d
```

## 📱 Mobile Access

1.  Start the server on your PC.
2.  Use `localtunnel` or `ngrok` to expose port 8001.
3.  Open the link on your phone to control the bot remotely!

## ⚠️ Disclaimer

This tool is for educational and internal productivity purposes. Use responsibly and adhere to the terms of service of the respective platforms.
