# 🦅 Raven — Risk & Portfolio Intelligence Engine

> Swiss-grade counterparty risk monitoring and portfolio analytics for digital asset wealth managers.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 (App Router) + Tailwind CSS + Recharts |
| Backend | FastAPI (Python 3.11) on Fly.io |
| Database | Supabase (PostgreSQL + TimescaleDB + RLS) |
| AI Agents | LangGraph + Claude (Anthropic API) |
| Task Queue | Celery + Redis |
| PDF Export | WeasyPrint + Jinja2 |
| Hosting | Vercel (frontend) + Fly.io (API) |

---

## Day 0 Setup (Do This First)

### 1. Accounts

- [ ] **GitHub** — create repo named `raven`, clone locally
- [ ] **Supabase** — [supabase.com](https://supabase.com) → New Project → Frankfurt/EU region → save DB password
- [ ] **Vercel** — [vercel.com](https://vercel.com) → connect GitHub
- [ ] **Fly.io** — `curl -L https://fly.io/install.sh | sh && fly auth login`

### 2. API Keys

- [ ] Anthropic: [console.anthropic.com](https://console.anthropic.com)
- [ ] CoinGecko: [coingecko.com/en/api](https://www.coingecko.com/en/api) (Demo key free)
- [ ] NewsAPI: [newsapi.org](https://newsapi.org)
- [ ] Supabase: Project Settings → API → copy URL, anon key, service role key

### 3. Database Setup

1. Go to Supabase → SQL Editor
2. Paste and run `scripts/001_schema.sql`
3. Paste and run `scripts/002_seed.sql`
4. Verify: you should see 25 counterparties in the `counterparties` table

---

## Local Development

### Prerequisites

```bash
# Python 3.11+
python --version

# Node.js 18+
node --version

# Redis (for Celery)
# macOS:
brew install redis && brew services start redis
# Linux:
sudo apt-get install redis-server && sudo service redis-server start
```

### Backend Setup

```bash
cd api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp ../.env.example .env
# Edit .env with your actual keys

# Start the API
uvicorn main:app --reload --port 8000
```

API will be available at: http://localhost:8000
Docs: http://localhost:8000/docs

### Frontend Setup

```bash
cd web

# Install dependencies
npm install

# Copy and fill in environment variables
cp .env.example .env.local
# Edit .env.local with your Supabase URL and anon key

# Start the dev server
npm run dev
```

Dashboard will be available at: http://localhost:3000

### Celery Worker (for async tasks)

```bash
cd api
source venv/bin/activate
celery -A app.workers.celery_app worker --loglevel=info
```

---

## Project Structure

```
raven/
├── api/                          # FastAPI backend
│   ├── main.py                   # App entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── fly.toml                  # Fly.io config
│   └── app/
│       ├── core/
│       │   ├── config.py         # Settings (env vars)
│       │   ├── database.py       # Supabase client
│       │   └── auth.py           # JWT + MFA auth
│       ├── routers/              # API endpoints
│       │   ├── auth.py
│       │   ├── counterparties.py
│       │   ├── portfolios.py
│       │   ├── reports.py
│       │   ├── alerts.py
│       │   ├── agents.py
│       │   └── stress_tests.py
│       ├── services/             # Business logic
│       │   ├── scoring_engine.py  ← THE CORE ASSET
│       │   ├── portfolio_analytics.py
│       │   ├── market_data.py
│       │   └── pdf_generator.py
│       ├── agents/               # LangGraph agent pipeline
│       │   ├── orchestrator.py
│       │   ├── scoring_agent.py
│       │   ├── portfolio_agent.py
│       │   ├── report_agent.py
│       │   └── tools/
│       └── workers/              # Celery tasks
│           ├── celery_app.py
│           ├── scoring.py
│           └── market_data.py
│
├── web/                          # Next.js frontend
│   ├── package.json
│   ├── next.config.js
│   └── src/
│       ├── app/                  # App Router pages
│       │   ├── layout.tsx
│       │   ├── dashboard/
│       │   ├── counterparties/
│       │   ├── portfolios/
│       │   ├── reports/
│       │   └── alerts/
│       ├── components/
│       │   ├── ui/               # Base components
│       │   ├── dashboard/        # Dashboard-specific
│       │   └── charts/           # Recharts wrappers
│       ├── lib/
│       │   ├── api.ts            # API client
│       │   └── supabase.ts       # Supabase client
│       └── types/
│           └── index.ts          # Shared TypeScript types
│
├── scripts/
│   ├── 001_schema.sql            # Database schema
│   └── 002_seed.sql              # Seed data
│
└── docs/                         # Architecture decisions
```

---

## Development Phases

| Phase | Weeks | Focus |
|-------|-------|-------|
| **1 — Foundation** | 1–3 | Schema, auth, counterparty registry, portfolio upload |
| **2 — Intelligence** | 4–7 | Scoring engine, agents, alert system |
| **3 — Report & Dashboard** | 8–10 | AI report generation, review UI, PDF export |
| **4 — Polish & Validate** | 11–12 | Security audit, pilot client, demo env |

---

## Scoring Model

The 6-dimension scoring engine (`api/app/services/scoring_engine.py`) is Raven's core asset.

| Dimension | Weight | Key Signals |
|-----------|--------|-------------|
| Regulatory Standing | 25% | Regulator tier, license status, jurisdiction |
| Financial Strength | 20% | Public listing, audited financials, capital ratio |
| Operational Resilience | 20% | SOC2/ISO27001, security incidents, insurance |
| Liquidity & Reserves | 15% | Proof of Reserves ratio, daily volume |
| On-Chain Health | 10% | Wallet reserve trend, TVL (DeFi) |
| Reputation & Market | 10% | News sentiment, social signals |

Scores are 0–100. Tiers: LOW (≥75), MEDIUM (≥55), HIGH (≥35), CRITICAL (<35).

All weights are configurable in `config.py` → `SCORING_WEIGHTS`.
Human overrides are logged to the immutable `audit_log` table.

---

## Key Rules

1. **Nothing in `scripts/002_seed.sql` is real client data.** Demo only.
2. **`audit_log` is immutable** — triggers prevent UPDATE/DELETE.
3. **No Non-MVP features.** If it's not in the MVP definition, escalate before building.
4. **All agent outputs require human review** before any PDF is generated.
5. **Service role key is backend-only.** Never expose to frontend or clients.
