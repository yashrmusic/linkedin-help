# UrbanMistrii Admin Bot (Recruitment Hub) 🏛️

**Internal Name**: `admin-aws-recruiter-urbanmistrii`
**Host**: AWS EC2 / Local
**Role**: The HR & Operations Manager for UrbanMistrii, Melange, and Deco Arte.

## 🌟 Core Operations
This bot is the central nervous system for our recruitment and operational workflows.

*   **Hiring Automation**: Manages job postings on LinkedIn, Internshala, and Naukri.
*   **Offer Intelligence**: Generates professional PDF offer letters from simple text prompts.
*   **Candidate Experience**: Automates applicant screening, messaging, and interview scheduling.
*   **Deep Memory**: Uses Gemini 1.5 Flash to parse resumes and understand candidate context.

## 🛠️ Architecture
*   **Brain**: `gemini-1.5-flash` (Google AI)
*   **Body**: Python FastAPI + Playwright (for browser automation)
*   **Face**: Glassmorphic "UrbanMistrii Admin" Dashboard
*   **Home**: `c:\Users\Asus\.gemini\antigravity\scratch\admin-aws-recruiter-urbanmistrii`

## 🚀 Quick Start
1.  **Activate**: `python app.py`
2.  **Access**: Open `http://localhost:8001`
3.  **Command**: Use the dashboard to triggering "Maintain Job" cycles or "Draft Offer".
