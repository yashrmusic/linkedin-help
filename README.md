# LinkedIn Free Job Applicant Messenger

Automated tool to send "Hello" messages to all applicants on your LinkedIn free job posts.

## ✨ Features

- 🚀 **Fast & Optimized** - Minimal wait times, quick execution
- 🔐 **Session Persistence** - Saves cookies, no need to login every time
- 📊 **Tracking** - Remembers who you've already messaged
- 📝 **Logging** - Full run log with timestamps
- 🛡️ **Error Handling** - Graceful recovery from failures

## 📋 Quick Start

### 1. Install Dependencies
```bash
pip install playwright python-dotenv
playwright install chromium
```

### 2. Configure Credentials
Create a `.env` file:
```env
LINKEDIN_EMAIL=your_email@example.com
LINKEDIN_PASSWORD=your_password
```

### 3. Run
```bash
python linkedin_messenger.py
```

## 📂 Files

| File | Purpose |
|------|---------|
| `linkedin_messenger.py` | **Main script** - run this |
| `.env` | Your LinkedIn credentials |
| `cookies.json` | Saved session (auto-generated) |
| `messaged_applicants.json` | Tracks messaged people |
| `run_log.txt` | Execution log with timestamps |

## 🔄 Workflow

```
START
  │
  ▼
┌─────────────────────────────────────┐
│ 1. LOGIN                            │
│    - Try saved cookies first        │
│    - Fall back to credentials       │
│    - Handle security verification   │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 2. NAVIGATE TO JOBS                 │
│    - Go to posted jobs page         │
│    - Click on first active job      │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 3. VIEW APPLICANTS                  │
│    - Click "View applicants"        │
│    - Extract all applicant profiles │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 4. MESSAGE EACH APPLICANT           │
│    For each applicant:              │
│    - Skip if already messaged       │
│    - Open profile                   │
│    - Click "Message"                │
│    - Type "Hello"                   │
│    - Click "Send"                   │
│    - Record as messaged             │
└─────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────┐
│ 5. SAVE & REPORT                    │
│    - Save cookies for next run      │
│    - Print summary statistics       │
└─────────────────────────────────────┘
  │
  ▼
 END
```

## 📊 Sample Output

```
[16:30:01] ==================================================
[16:30:01] 🚀 LINKEDIN APPLICANT MESSENGER
[16:30:01] ==================================================
[16:30:01] 📧 Account: jobs@example.com
[16:30:01] 🎯 Target: https://www.linkedin.com/my-items/posted-jobs/
[16:30:01] 
[16:30:02] 🔐 Starting login...
[16:30:02]    Trying saved session...
[16:30:04] ✅ Logged in via cookies!
[16:30:04] 📋 Navigating to: https://www.linkedin.com/my-items/posted-jobs/
[16:30:07] ✅ Opened job post
[16:30:07] 👥 Opening applicants...
[16:30:09] ✅ Viewing applicants
[16:30:09] 🔍 Finding applicants...
[16:30:10] 📊 Found 3 applicant profiles, 3 message buttons
[16:30:10] 📨 Messaging 3 applicants...
[16:30:10] [1/3] Messaging: john-doe...
[16:30:14]    ✅ Sent!
[16:30:14] [2/3] Messaging: jane-smith...
[16:30:18]    ✅ Sent!
[16:30:18] [3/3] Messaging: alex-kumar...
[16:30:22]    ✅ Sent!
[16:30:22] 
[16:30:22] ==================================================
[16:30:22] 📊 SUMMARY REPORT
[16:30:22] ==================================================
[16:30:22]    Applicants found:   3
[16:30:22]    Messages sent:      3
[16:30:22]    Already messaged:   0
[16:30:22]    Failed:             0
[16:30:22] ==================================================
[16:30:22] ✅ Session saved. Run again to message new applicants.
```

## ⚠️ Important Notes

1. **Security Verification**: If LinkedIn asks for verification, complete it manually in the browser
2. **Rate Limiting**: The script includes delays to avoid detection
3. **Message Content**: Currently sends "Hello" - modify `MESSAGE_TEXT` in the script to change
4. **Multiple Jobs**: Currently processes the first job - run again after checking all jobs

## 🔧 Customization

Edit `linkedin_messenger.py` to change:

```python
# Message to send (line ~50)
MESSAGE_TEXT = "Hello"

# Wait times (lines ~45-48)
FAST_WAIT = 1000      # Quick operations
MEDIUM_WAIT = 2000    # Page transitions  
SLOW_WAIT = 3000      # Heavy page loads
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| "Login failed" | Check credentials in `.env` |
| "No jobs found" | Ensure you have an active free job post |
| "No applicants" | Wait for applicants to apply |
| Security verification | Complete it manually in browser |

## 📜 License

For personal use only. Use responsibly.
