# 🤖 AI Code Review System

> An AI-powered GitHub App that automatically reviews pull requests, flags security vulnerabilities, suggests architectural improvements, and posts inline comments — all within seconds of a PR being opened.

**[🚀 Live Dashboard](https://ai-code-review-dashboard-seven.vercel.app)** · 
**[⚙️ Backend API](https://ai-code-review-production-ec4d.up.railway.app/api/repos)**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet-purple.svg)](https://anthropic.com)
[![Railway](https://img.shields.io/badge/Deployed-Railway-red.svg)](https://railway.app)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📸 Demo

When a pull request is opened, the system automatically posts inline review comments like this:

```
🔴 Critical
This function has no zero-division check — will throw ZeroDivisionError when b=0.
Consider adding: if b == 0: raise ValueError("Cannot divide by zero")

🟡 Warning
store_user() logs the plaintext password on line 47. Remove the print statement
and use a hashing library like bcrypt before storing credentials.

🔵 Suggestion  
process_file() opens a file handle but never closes it. Use a context manager:
with open(filepath, 'r') as f: content = f.read()
```

---



## ✨ Features

- **Inline PR comments** — feedback attached to exact lines in the diff, not just a wall of text
- **Security scanning** — flags SQL injection, shell injection, hardcoded credentials, insecure deserialization
- **Severity levels** — 🔴 Critical / 🟡 Warning / 🔵 Suggestion so developers know what to fix first
- **Smart filtering** — skips lock files, binaries, minified assets, and bot-authored PRs
- **Idempotency** — never posts duplicate reviews even if GitHub retries the webhook
- **Context-aware** — sends PR title and description to the AI so it understands intent
- **Multi-file support** — reviews up to 20 files per PR, prioritised by change size
- **Error resilience** — posts a failure comment if something goes wrong so developers aren't left wondering

---

## 🏗️ Architecture

```
GitHub PR opened
       │
       ▼
  Webhook Event
  (POST /webhook)
       │
       ▼
┌─────────────────────────────────────────┐
│           FastAPI Server                │
│                                         │
│  1. Verify HMAC-SHA256 signature        │
│  2. Parse PR payload → PREvent          │
│  3. Check idempotency (SQLite)          │
│  4. Queue background task               │
│  5. Return 200 immediately              │
└─────────────────────────────────────────┘
       │
       ▼ (background)
┌─────────────────────────────────────────┐
│         Review Pipeline                 │
│                                         │
│  github_client.py                       │
│  ├── GitHub App JWT auth                │
│  ├── Fetch PR diff (paginated)          │
│  └── Filter non-reviewable files        │
│                                         │
│  reviewer.py                            │
│  ├── Prioritise files by change size    │
│  ├── Build structured prompt            │
│  └── Call Claude Sonnet API             │
│                                         │
│  comment_poster.py                      │
│  ├── Parse AI JSON response             │
│  ├── Post inline review comments        │
│  └── Post summary to conversation       │
└─────────────────────────────────────────┘
       │
       ▼
  Comments appear
  on GitHub PR
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web server | FastAPI + Uvicorn | Webhook receiver, async request handling |
| AI model | Claude Sonnet (Anthropic) | Code analysis and review generation |
| GitHub integration | GitHub Apps API | Authentication, diff fetching, comment posting |
| Storage | SQLite | Idempotency tracking |
| Deployment | Railway | 24/7 cloud hosting |
| Auth | JWT + RSA | GitHub App authentication |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- A GitHub account
- An [Anthropic API key](https://console.anthropic.com)
- [ngrok](https://ngrok.com) for local development

### 1. Clone the repo

```bash
git clone https://github.com/AbhishekSanthkumar/AI-Code-Review.git
cd AI-Code-Review
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a GitHub App

1. Go to GitHub → Settings → Developer Settings → GitHub Apps → **New GitHub App**
2. Set webhook URL to your ngrok URL + `/webhook`
3. Set permissions: **Pull requests: Read & Write**, **Contents: Read**
4. Generate and download a private key `.pem` file
5. Note your **App ID**

### 5. Configure environment variables

Create a `.env` file in the project root:

```env
GITHUB_APP_ID=your_app_id
GITHUB_PRIVATE_KEY_PATH=./your-private-key.pem
GITHUB_WEBHOOK_SECRET=your_webhook_secret
ANTHROPIC_API_KEY=sk-ant-...
DB_PATH=./reviews.db
```

### 6. Start the server

```bash
# Start ngrok in one terminal
ngrok http 8000

# Start the server in another terminal
uvicorn main:app --reload --port 8000
```

### 7. Install the GitHub App on a repo

Go to your GitHub App settings → **Install App** → select a repository.

Open a pull request — you should see the AI review appear within 15 seconds.

---

## ☁️ Deployment (Railway)

This project is configured for one-click deployment to Railway.

1. Fork this repo
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Add these environment variables in Railway:

```
GITHUB_APP_ID         = your app id
GITHUB_PRIVATE_KEY_B64 = base64 encoded contents of your .pem file
GITHUB_WEBHOOK_SECRET = your webhook secret
ANTHROPIC_API_KEY     = sk-ant-...
DB_PATH               = ./reviews.db
```

To base64 encode your private key:
```bash
python -c "
import base64
with open('your-key.pem', 'rb') as f:
    print(base64.b64encode(f.read()).decode('utf-8'))
"
```

4. Update your GitHub App webhook URL to your Railway domain + `/webhook`

---

## 📁 Project Structure

```
ai-code-review/
├── main.py            # FastAPI app, webhook endpoint, PR event routing
├── github_client.py   # GitHub App auth, diff fetching
├── reviewer.py        # AI prompt building, Claude API call, response parsing
├── comment_poster.py  # Posting inline comments and summary back to GitHub
├── storage.py         # SQLite idempotency tracking
├── Procfile           # Railway deployment config
├── railway.json       # Railway build settings
├── requirements.txt   # Python dependencies
└── .gitignore         # Keeps secrets out of git
```

---

## 🔒 Security

- Webhook payloads verified with HMAC-SHA256 before processing
- GitHub App private key stored as base64 env var — never committed to git
- `hmac.compare_digest()` used for signature comparison (timing-attack safe)
- Bot and Dependabot PRs automatically skipped
- Draft PRs skipped to avoid reviewing work-in-progress

---

## 🗺️ Roadmap

- [ ] Dashboard for tracking code quality metrics over time
- [ ] Support for GitLab and Bitbucket webhooks
- [ ] Fine-tuned model on real code review datasets
- [ ] Per-repo configuration (custom rules, severity thresholds)
- [ ] Slack/Teams notifications for critical findings
- [ ] PR quality score trending over time

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

[MIT](LICENSE)

---

## 👤 Author

**Abhishek Santhkumar**  
Built as part of a portfolio project to demonstrate AI integration, GitHub App development, and production deployment skills.

> ⭐ If this project helped you, please give it a star on GitHub!
