# Priva-Search — AI Coding Assistant System Instructions
**Project:** Priva-Search  
**Version:** 2.0  
**Purpose:** This file is the single source of truth for any AI coding assistant working on this project. Read this fully before writing any code, suggesting any architecture, or making any file changes.

---

## 1. Project Overview

Priva-Search is a consumer-facing web application that lets users search for any brand and instantly receive a **Privacy Scorecard** — a human-readable breakdown of how that company handles personal data, based on AI analysis of their official privacy policy.

The app is designed around three core principles:
1. **Accuracy over speed** — bad data is worse than slow data
2. **Transparency** — users always see the source text behind every score
3. **Action** — users can opt out of data collection directly from the app

---

## 2. Full Tech Stack

Never suggest alternatives to these unless the user explicitly asks. Do not introduce new dependencies without asking first.

### Frontend
| Tool | Version | Purpose |
|---|---|---|
| Next.js | 16 | App framework, routing, SSR |
| React | 19 | UI components |
| Tailwind CSS | 4 | Styling and layout |
| Framer Motion | Latest | Animations (card expansion, transitions) |
| TypeScript | 5 | Strict typing throughout |

### Backend
| Tool | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Backend language |
| FastAPI | Latest | API framework, including WebSocket support |
| Pydantic | v2 | Data validation and schema enforcement |
| SQLAlchemy | 2.0 | ORM for PostgreSQL |
| APScheduler | Latest | Background re-crawl jobs |
| Firecrawl | Latest | Privacy policy crawling and Markdown conversion |
| httpx | Latest | Async HTTP client (fallback crawling, brand discovery) |
| RQ (Redis Queue) | Latest | Async job queue for scan pipeline |
| slowapi | Latest | Rate limiting middleware for FastAPI |

### Database
| Tool | Purpose |
|---|---|
| PostgreSQL 16 | Primary database for all scorecards, cache, and snippets |
| Redis | **Required** — job queue (RQ), rate limiting, Groq usage counter, WebSocket pub/sub |

### AI Layer
| Model | Provider | Role |
|---|---|---|
| Llama 3.3 70B | Groq API (free tier) | Primary analysis engine |
| Qwen2.5 7B Instruct | Ollama (local, NVIDIA CUDA) | Fallback when Groq rate limit is hit |

### DevOps / Environment
| Tool | Purpose |
|---|---|
| Docker + Docker Compose | Local development environment |
| `.env` files | All secrets and API keys |
| pytest | Backend testing |
| Vitest | Frontend testing |

---

## 3. Repository Structure

Always follow this structure exactly. Never create files outside of it without asking.

```
priva-search/
├── frontend/
│   ├── app/
│   │   ├── page.tsx                   # Home — search UI
│   │   ├── brand/
│   │   │   └── [slug]/
│   │   │       └── page.tsx           # Scorecard page for a brand
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── SearchBar.tsx              # Main search input
│   │   ├── NutritionLabel.tsx         # The 5-category scorecard card
│   │   ├── RiskCategory.tsx           # Individual expandable risk row
│   │   ├── SnippetDrawer.tsx          # Source text reveal panel
│   │   ├── TrustBadge.tsx             # Verified / AI-Generated / Stale badge
│   │   ├── OptOutButton.tsx           # "Take Action" CTA
│   │   ├── ScanProgress.tsx           # WebSocket-driven live progress bar
│   │   └── ScoreExplanation.tsx       # score_reason + risk_examples panel
│   ├── lib/
│   │   ├── api.ts                     # All REST calls to FastAPI backend
│   │   ├── socket.ts                  # WebSocket client for scan progress
│   │   └── types.ts                   # Shared TypeScript types
│   └── public/
│
├── backend/
│   ├── main.py                        # FastAPI app entry point
│   ├── routers/
│   │   ├── search.py                  # GET /search?q=spotify
│   │   ├── scan.py                    # POST /scan, WS /ws/scan/{scan_id}
│   │   ├── brand.py                   # GET /brand/{slug}
│   │   └── optout.py                  # GET /optout/{brand_slug}
│   ├── services/
│   │   ├── crawler.py                 # Firecrawl + fallback chain
│   │   ├── brand_discovery.py         # Domain resolution from brand name
│   │   ├── analyzer.py                # AI model routing (Groq → Ollama fallback)
│   │   ├── validator.py               # JSON schema enforcement + confidence check
│   │   ├── scheduler.py               # APScheduler re-crawl jobs
│   │   ├── groq_tracker.py            # Groq daily usage counter (Redis)
│   │   └── rate_limiter.py            # IP-based and global rate limiting
│   ├── workers/
│   │   └── scan_worker.py             # RQ worker — runs the scan pipeline
│   ├── models/
│   │   ├── brand.py
│   │   ├── scorecard.py
│   │   └── snippet.py
│   ├── schemas/
│   │   ├── scorecard.py
│   │   └── analysis.py
│   ├── db/
│   │   ├── database.py
│   │   └── migrations/
│   ├── prompts/
│   │   └── systemInstruction.md       # System prompt for the privacy analysis AI
│   ├── tests/
│   └── .env
│
├── docker-compose.yml
└── README.md
```

---

## 4. Core Features & Behavior

### 4.1 The Two-Tier Data Model
This is critical. Always implement this distinction.

- **Tier 1 — Curated (Top 200 brands):** Pre-analyzed, manually reviewed entries stored in the database. Return these instantly. Display a green **"Verified"** badge.
- **Tier 2 — Live Scan (everything else):** Trigger an async queue job via RQ. Display a yellow **"AI-Generated"** badge. Never present these as verified facts.

### 4.2 The Nutrition Label (5 Risk Categories)
Every scorecard must display exactly these five categories, each scored 1–10 (1 = best privacy, 10 = worst):

1. **Data Selling** — Does the company sell user data for profit?
2. **AI Training** — Is user data used to train AI/ML models?
3. **Third-Party Sharing** — How broadly is data shared outside the company?
4. **Data Retention** — How long is data kept after a user leaves?
5. **Deceptive UX** — Does the policy rely on dark patterns for consent?

Each category must also display:
- `score_reason` — a 1–2 sentence explanation of *why* that score was given
- `risk_examples` — up to 3 concrete examples extracted from the policy text

### 4.3 Trust & Freshness
- Every scorecard must show a **"Last Scanned"** date
- Policies not re-scanned within **60 days** must display a **"Stale"** warning
- APScheduler re-crawls all stored policies every **30 days** automatically
- Before re-crawling, compare the new policy's `policy_hash` (SHA-256 of the raw markdown) to the stored hash. If identical → skip re-analysis, update `last_scanned_at` only. This avoids unnecessary AI calls.

### 4.4 The Opt-Out ("Take Action") Button
- Check the stored `do_not_sell_url` or `deletion_request_url` from the scorecard
- If a URL exists → render a direct link to it
- If no URL exists → generate a pre-filled opt-out email using the `privacy_contact_email` field and open `mailto:` with the body pre-populated
- Never claim the opt-out is guaranteed — frame it as "sending a request"

---

## 5. The Async Scan Pipeline

The scan pipeline is fully asynchronous. No scan work is ever done synchronously in a request handler.

### 5.1 Queue Architecture (RQ + Redis)

```
POST /scan
  └─► Enqueue job in Redis (RQ)
        └─► scan_worker.py picks up job
              ├─► brand_discovery.py  (find domain)
              ├─► crawler.py          (get policy markdown)
              ├─► analyzer.py         (AI analysis)
              ├─► validator.py        (validate output)
              └─► DB write + WS notify
```

The worker publishes progress events to a Redis pub/sub channel (`scan:{scan_id}:progress`) at each stage. The FastAPI WebSocket endpoint subscribes to this channel and forwards events to the connected frontend client.

**Job stages and their WebSocket event payloads:**
```json
{ "stage": "queued",     "message": "Your scan is queued",          "progress": 5  }
{ "stage": "discovery",  "message": "Finding privacy policy URL",   "progress": 20 }
{ "stage": "crawling",   "message": "Reading privacy policy",       "progress": 40 }
{ "stage": "analyzing",  "message": "AI is analyzing the policy",   "progress": 65 }
{ "stage": "validating", "message": "Verifying results",            "progress": 85 }
{ "stage": "done",       "message": "Scan complete",                "progress": 100, "slug": "spotify" }
{ "stage": "failed",     "message": "Human-readable error message", "progress": 0   }
```

### 5.2 Brand Discovery (brand_discovery.py)

When a user searches for a brand name (e.g., "spotify"), the system must resolve it to a domain and then find the privacy policy URL. Use this priority chain:

```
1. Check brands table — if domain already stored, use it
2. Query DuckDuckGo Instant Answer API (free, no key required)
   → GET https://api.duckduckgo.com/?q=spotify+official+site&format=json
3. Construct candidate URL: {brand_slug}.com
4. Attempt to find privacy URL via Firecrawl sitemap crawl
5. Try common privacy URL patterns:
   - /privacy
   - /privacy-policy
   - /legal/privacy
   - /about/privacy
```

Never use Clearbit (paid). DuckDuckGo + pattern matching is sufficient. Store the resolved domain in the `brands` table so future searches skip discovery entirely.

### 5.3 Crawl Fallback Chain (crawler.py)

Firecrawl will fail on some sites. Always use this fallback order — never give up after step 1:

```
1. Firecrawl (primary) — best quality Markdown output
2. sitemap.xml parsing — find privacy URL from sitemap
3. Direct httpx GET — fetch the raw HTML, convert to Markdown with markdownify
4. Google Cache — GET https://webcache.googleusercontent.com/search?q=cache:{url}
5. Fail gracefully — return { "crawl_status": "failed", "reason": "..." }
```

Log which method succeeded for every crawl. If Firecrawl fails more than 3 times in a row on a domain, flag it in the `brands` table as `crawl_blocked: true` so future scans skip straight to fallback methods.

### 5.4 AI Model Routing (analyzer.py)

```python
async def analyze_policy(markdown_text: str) -> dict:
    if await groq_tracker.is_limit_approaching():   # >80% of daily quota used
        return await analyze_with_ollama(markdown_text)
    try:
        return await analyze_with_groq(markdown_text)
    except RateLimitError:
        await groq_tracker.mark_limit_hit()
        return await analyze_with_ollama(markdown_text)
```

**Groq API settings:**
- Model: `llama-3.3-70b-versatile`
- Free tier limits: 14,400 requests/day, 6,000 tokens/minute
- Always set `response_format: { type: "json_object" }` in the API call
- Max tokens for response: 2048

**Ollama settings:**
- Model: `qwen2.5:7b`
- Runs locally via CUDA on the developer's NVIDIA GPU
- Base URL: `http://localhost:11434`
- Always use the `/api/chat` endpoint with `format: "json"`

### 5.5 Groq Usage Tracker (groq_tracker.py)

Track Groq API usage in Redis with a daily counter that auto-expires at midnight UTC.

```python
# Redis key pattern: groq:usage:{YYYY-MM-DD}
# Increment on every successful Groq call
# Read before every call to check against limit

GROQ_DAILY_LIMIT = 14400
GROQ_WARNING_THRESHOLD = 0.80   # Switch to Ollama at 80%
```

### 5.6 Output Validation (validator.py)

Raw AI output is **never** passed directly to the frontend. Always run it through the validator first.

The validator must:
1. Check that the response is valid JSON — reject and retry if not (max 2 retries)
2. Validate against the Pydantic `AnalysisOutput` schema
3. Check that all 5 categories are present
4. Check that all scores are integers in range 1–10
5. Check that all confidence values are integers in range 0–100
6. Check that `score_reason` and `risk_examples` are present for each category
7. If any category confidence is ≤ 40 → set `legal_review_recommended: true`
8. If any category score is ≥ 8 → set `legal_review_recommended: true`

### 5.7 The System Prompt
The AI system prompt for privacy analysis is stored in `backend/prompts/systemInstruction.md`. Load it from the file at runtime — never hardcode it in Python.

```python
def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "systemInstruction.md"
    return prompt_path.read_text(encoding="utf-8")
```

---

## 6. Database Schema

### brands
```sql
id                SERIAL PRIMARY KEY
name              VARCHAR(255) NOT NULL
slug              VARCHAR(255) UNIQUE NOT NULL   -- e.g. "spotify"
domain            VARCHAR(255)                   -- e.g. "spotify.com"
privacy_url       TEXT
tier              SMALLINT NOT NULL DEFAULT 2    -- 1 = curated, 2 = live scan
crawl_blocked     BOOLEAN DEFAULT FALSE          -- true if site blocks all crawlers
created_at        TIMESTAMP DEFAULT NOW()
```

### scorecards
```sql
id                        SERIAL PRIMARY KEY
brand_id                  INTEGER REFERENCES brands(id)
overall_risk_score        SMALLINT
overall_confidence        SMALLINT
summary                   TEXT
trust_status              VARCHAR(20)   -- 'verified', 'ai_generated', 'stale', 'needs_review'
last_scanned_at           TIMESTAMP
raw_markdown_snapshot     TEXT
policy_hash               VARCHAR(64)   -- SHA-256 of raw_markdown_snapshot, used to detect policy changes
model_used                VARCHAR(50)   -- 'llama-3.3-70b' or 'qwen2.5:7b'
crawl_method_used         VARCHAR(30)   -- 'firecrawl', 'sitemap', 'direct', 'google_cache'
legal_review_recommended  BOOLEAN DEFAULT FALSE
created_at                TIMESTAMP DEFAULT NOW()
```

### risk_categories
```sql
id                SERIAL PRIMARY KEY
scorecard_id      INTEGER REFERENCES scorecards(id)
category_key      VARCHAR(50)   -- 'data_selling', 'ai_training', etc.
score             SMALLINT
confidence        SMALLINT
found             BOOLEAN
plain_summary     TEXT
score_reason      TEXT          -- Why this score was given (1-2 sentences)
risk_examples     JSONB         -- Array of up to 3 concrete examples from the policy
snippet           TEXT
extra_data        JSONB
```

### opt_out_info
```sql
id                      SERIAL PRIMARY KEY
scorecard_id            INTEGER REFERENCES scorecards(id)
gpc_supported           BOOLEAN
do_not_sell_url         TEXT
deletion_request_url    TEXT
privacy_contact_email   VARCHAR(255)
opt_out_notes           TEXT
```

### scan_jobs
```sql
id              VARCHAR(36) PRIMARY KEY    -- UUID
brand_name      VARCHAR(255)
status          VARCHAR(20)                -- 'queued', 'discovery', 'crawling', 'analyzing', 'validating', 'done', 'failed'
error_message   TEXT
ip_address      VARCHAR(45)               -- for abuse tracking
created_at      TIMESTAMP DEFAULT NOW()
completed_at    TIMESTAMP
```

---

## 7. API Endpoints

### GET `/search`
**Query params:** `q` (brand name string)
**Rate limit:** 30 requests/minute per IP
**Behavior:** Check the database for a matching brand. If found and not stale → return cached scorecard instantly. If stale or not found → enqueue a scan job and return `202 Accepted` with a `scan_id`.

### POST `/scan`
**Body:** `{ "brand_name": "string", "domain": "string (optional)" }`
**Rate limit:** 5 requests/minute per IP, 100/day per IP
**Behavior:** Enqueues a scan job in RQ. Returns `{ "scan_id": "uuid" }` immediately. Does not wait for the job to complete.

### WebSocket `/ws/scan/{scan_id}`
**Behavior:** Client connects and receives real-time JSON progress events as the scan advances through each stage. Closes automatically when stage is `done` or `failed`. Falls back gracefully if WebSocket is unavailable — the frontend can poll `/scan/{scan_id}/status` instead.

### GET `/scan/{scan_id}/status`
**Behavior:** Polling fallback. Returns the current status and progress percentage of a scan job.

### GET `/brand/{slug}`
**Behavior:** Returns the full scorecard for a brand by slug, including all 5 risk categories with `score_reason` and `risk_examples`.

### GET `/optout/{slug}`
**Behavior:** Returns opt-out information and generates the email template if no direct URL is available.

---

## 8. Abuse Protection

All public-facing endpoints must be protected. Never skip this.

### Rate Limiting (slowapi + Redis)
```python
# Per-IP limits — enforced via slowapi middleware
GET  /search          → 30 requests/minute
POST /scan            → 5 requests/minute, 100 requests/day
WS   /ws/scan/{id}    → 10 concurrent connections per IP
GET  /brand/{slug}    → 60 requests/minute
```

### Scan Abuse Prevention
- Reject any `POST /scan` where `brand_name` is a raw IP address or localhost
- Reject any domain that is not a valid public TLD
- If a single IP submits more than 20 unique brand scans in one hour → temporarily block for 1 hour and log the incident
- Store `ip_address` on every `scan_jobs` record for audit purposes

### Future CAPTCHA Hook
Add a `captcha_required` flag to the `/search` response. When the backend detects suspicious traffic patterns (e.g., >10 searches/minute from one IP), set this flag to `true`. The frontend should render a CAPTCHA challenge before allowing the next scan. CAPTCHA integration is deferred to v2 but the hook must exist in v1.

---

## 9. Coding Standards

### General
- Always use **TypeScript** on the frontend — no `.js` files in the `frontend/` directory
- Always use **type hints** in Python — no untyped functions
- Always use **async/await** for all I/O operations — no blocking calls
- Never commit `.env` files — always use `.env.example` with placeholder values
- All API keys go in environment variables — never hardcode them

### Python Style
- Follow **PEP 8** strictly
- Use **Pydantic v2** models for all request/response schemas
- Use **SQLAlchemy 2.0 async** sessions — not the legacy sync API
- All service functions must have docstrings
- Use structured logging with Python's built-in `logging` module and JSON formatter

### TypeScript / React Style
- Use **functional components only** — no class components
- All props must have explicit TypeScript interfaces
- Use **React Query (TanStack Query)** for all REST data fetching and cache management
- Use native browser `WebSocket` (wrapped in a custom hook) for scan progress — do not use socket.io
- Never use the `any` type — use `unknown` and narrow appropriately
- Component files use **PascalCase** (`NutritionLabel.tsx`)
- Utility files use **camelCase** (`api.ts`, `socket.ts`)

### Error Handling
- Every API route must return structured error responses: `{ "error": "string", "detail": "string" }`
- The frontend must handle all three states for async data: **loading**, **error**, **success**
- Never show raw backend error messages in the UI — always map them to user-friendly strings
- WebSocket disconnections must be handled gracefully — fall back to polling automatically

---

## 10. Environment Variables

The following variables are required. Always check for them at startup and throw a clear error if any are missing.

```env
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/privasearch
REDIS_URL=redis://localhost:6379/0
GROQ_API_KEY=your_groq_api_key_here
OLLAMA_BASE_URL=http://localhost:11434
FIRECRAWL_API_KEY=your_firecrawl_api_key_here
RESCAN_INTERVAL_DAYS=30
STALE_THRESHOLD_DAYS=60
MIN_CONFIDENCE_THRESHOLD=40
GROQ_DAILY_LIMIT=14400
GROQ_WARNING_THRESHOLD=0.80
RATE_LIMIT_SCAN_PER_MINUTE=5
RATE_LIMIT_SCAN_PER_DAY=100
RATE_LIMIT_SEARCH_PER_MINUTE=30

# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## 11. What NOT To Do

- **Do not use any paid AI APIs** other than Groq's free tier. Never suggest OpenAI, Anthropic, or Cohere unless explicitly asked.
- **Do not use any paid database services** — PostgreSQL and Redis run locally via Docker.
- **Do not use Prisma** — the project uses SQLAlchemy.
- **Do not use create-react-app** — the project uses Next.js.
- **Do not use axios** — use `httpx` on the backend and native `fetch` or React Query on the frontend.
- **Do not use socket.io** — use native browser WebSocket with a custom hook.
- **Do not use Clearbit** — it is paid. Use DuckDuckGo Instant Answer API for brand discovery.
- **Do not run scan jobs synchronously inside request handlers** — all scans go through RQ.
- **Do not skip the validation layer** — raw AI output must never reach the database or frontend directly.
- **Do not cache stale data silently** — always surface the "Last Scanned" date and stale indicator to the user.
- **Do not re-analyze a policy if the hash has not changed** — check `policy_hash` before triggering AI.
- **Do not make the opt-out sound guaranteed** — it is a user-submitted request, not an automated process.
- **Do not add any analytics, tracking pixels, or third-party scripts** to the frontend — the product is about privacy; it must practice what it preaches.

---

## 12. Key Business Logic Reference

| Rule | Value |
|---|---|
| Re-crawl interval | Every 30 days |
| Stale threshold | 60 days since last scan |
| Score range | 1 (best) to 10 (worst) |
| Confidence range | 0 to 100 |
| Low confidence cutoff | ≤ 40 triggers "Needs Review" flag |
| High risk cutoff | ≥ 8 triggers "Legal Review Recommended" flag |
| AI retry limit | 2 retries on invalid JSON output |
| Groq daily request limit | 14,400 |
| Groq auto-fallback threshold | 80% of daily limit |
| Ollama model | qwen2.5:7b |
| Max snippet length | 300 characters per category |
| Curated brand count | 200 (Tier 1) |
| Scan rate limit | 5/min, 100/day per IP |
| Search rate limit | 30/min per IP |
| Abuse block threshold | 20 unique brand scans/hour from one IP |
| Policy hash algorithm | SHA-256 |
| Crawl fallback order | Firecrawl → sitemap.xml → direct httpx → Google Cache |
| Brand discovery method | DB lookup → DuckDuckGo → pattern matching |
| WebSocket progress stages | queued → discovery → crawling → analyzing → validating → done |
