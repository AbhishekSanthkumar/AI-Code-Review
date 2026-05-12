# 🤖 AI Code Review System

> An AI-powered GitHub App that automatically reviews pull requests, flags security vulnerabilities, suggests architectural improvements, and posts inline comments all within seconds of a PR being opened.

**[🚀 Live Dashboard](https://ai-code-review-dashboard-seven.vercel.app)** · 
**[⚙️ Backend API](https://ai-code-review-production-ec4d.up.railway.app/api/repos)**

[![CI](https://github.com/AbhishekSanthkumar/AI-Code-Review/actions/workflows/ci.yml/badge.svg)](https://github.com/AbhishekSanthkumar/AI-Code-Review/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet-purple.svg)](https://anthropic.com)
[![Railway](https://img.shields.io/badge/Backend-Railway-red.svg)](https://railway.app)
[![Vercel](https://img.shields.io/badge/Dashboard-Vercel-black.svg)](https://vercel.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📸 Demo

When a pull request is opened, the system automatically posts inline review comments directly on the diff:

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

The live dashboard at **[ai-code-review-dashboard-seven.vercel.app](https://ai-code-review-dashboard-seven.vercel.app)** tracks code quality trends over time — click any PR row to see the full breakdown of every comment posted.

---

## ✨ Features

- **Inline PR comments** - feedback attached to exact lines in the diff, not just a wall of text
- **Security scanning** - flags SQL injection, shell injection, hardcoded credentials, insecure deserialization
- **Severity levels** - 🔴 Critical / 🟡 Warning / 🔵 Suggestion so developers know what to fix first
- **Smart filtering** - skips lock files, binaries, minified assets, and bot-authored PRs
- **Idempotency** - never posts duplicate reviews even if GitHub retries the webhook
- **Context-aware** - sends PR title and description to the AI so it understands intent
- **Multi-file support** - reviews up to 20 files per PR, prioritised by change size
- **Error resilience** - posts a failure comment if something goes wrong so developers aren't left wondering
- **Metrics dashboard** - code quality score trends, most critical files, author leaderboards
- **PR detail view** - click any PR to see the full text of every review comment

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
│                                         │
│  storage.py                             │
│  ├── Save review + comment data         │
│  └── Idempotency check                  │
└─────────────────────────────────────────┘
       │
       ▼
  Comments appear          Metrics saved
  on GitHub PR        →    to SQLite DB
                                │
                                ▼
                    ┌───────────────────────┐
                    │   React Dashboard     │
                    │   (Vercel)            │
                    │                       │
                    │  Score trend chart    │
                    │  Critical files list  │
                    │  Author leaderboard   │
                    │  PR history table     │
                    │  Comment detail modal │
                    └───────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web server | FastAPI + Uvicorn | Webhook receiver, async request handling |
| AI model | Claude Sonnet (Anthropic) | Code analysis and review generation |
| GitHub integration | GitHub Apps API | Authentication, diff fetching, comment posting |
| Storage | SQLite + Railway Volume | Review metrics, idempotency tracking |
| Backend deployment | Railway | 24/7 cloud hosting with persistent storage |
| Auth | JWT + RSA | GitHub App authentication |
| Dashboard | React 18 + Vite | Code quality metrics frontend |
| Styling | Tailwind CSS | Dashboard design |
| Charts | Recharts | Score trend visualisation |
| Data fetching | TanStack Query | API state management |
| Dashboard deployment | Vercel | Static frontend hosting |
| CI/CD | GitHub Actions | Automated test suite on every push |

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
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

## 📊 Running the Dashboard Locally

```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:5173` - the dashboard connects to the live Railway API automatically.

---

## ☁️ Deployment

### Backend (Railway)

1. Fork this repo
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Add a **Volume** mounted at `/data`
4. Add these environment variables:

```
GITHUB_APP_ID          = your app id
GITHUB_PRIVATE_KEY_B64 = base64 encoded contents of your .pem file
GITHUB_WEBHOOK_SECRET  = your webhook secret
ANTHROPIC_API_KEY      = sk-ant-...
```

To base64 encode your private key:
```bash
python -c "
import base64
with open('your-key.pem', 'rb') as f:
    print(base64.b64encode(f.read()).decode('utf-8'))
"
```

5. Update your GitHub App webhook URL to your Railway domain + `/webhook`

### Dashboard (Vercel)

1. Push the `dashboard/` folder to a separate GitHub repo
2. Go to [vercel.com](https://vercel.com) → **New Project** → import the repo
3. Vercel auto-detects Vite — click **Deploy**

---

## 📁 Project Structure

```
ai-code-review/
├── main.py            # FastAPI app, webhook endpoint, PR event routing
├── github_client.py   # GitHub App auth, diff fetching
├── reviewer.py        # AI prompt building, Claude API call, response parsing
├── comment_poster.py  # Posting inline comments and summary back to GitHub
├── storage.py         # SQLite schema, metrics storage, idempotency
├── api.py             # REST API endpoints for the dashboard
├── test_main.py       # Test suite (7 tests)
├── Procfile           # Railway deployment config
├── railway.json       # Railway build settings
├── requirements.txt   # Python dependencies
└── .gitignore         # Keeps secrets out of git

dashboard/
├── src/
│   ├── App.jsx        # Full dashboard — charts, tables, comment modal
│   └── index.css      # Tailwind import
├── vite.config.js
└── package.json
```

---

## 🔒 Security

- Webhook payloads verified with HMAC-SHA256 before processing
- GitHub App private key stored as base64 env var — never committed to git
- `hmac.compare_digest()` used for signature comparison (timing-attack safe)
- Bot and Dependabot PRs automatically skipped
- Draft PRs skipped to avoid reviewing work-in-progress
- CORS locked to dashboard domain in production

---

## 🗺️ Roadmap

- [x] AI-powered inline PR review comments
- [x] Idempotency - no duplicate reviews on webhook retries
- [x] CI pipeline with automated test suite
- [x] Production deployment on Railway
- [x] Metrics dashboard with score trends
- [x] PR detail view showing full comment text
- [ ] Support for GitLab and Bitbucket webhooks
- [ ] Fine-tuned model on real code review datasets
- [ ] Per-repo configuration (custom rules, severity thresholds)
- [ ] Slack/Teams notifications for critical findings

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

[MIT](LICENSE)

---

## 👤 Author

**Abhishek Santhkumar**  
Built as a portfolio project demonstrating AI integration, GitHub App development, full-stack engineering, and production deployment.

> ⭐ If this project helped you, please give it a star on GitHub!
