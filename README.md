# Priva-Search

> Know who's selling your data before you sign up.

Priva-Search is a consumer-facing web app that lets users paste a link to any privacy policy and instantly receive a **Privacy Scorecard** — a human-readable breakdown of how that company handles personal data, based on AI analysis of their official privacy policy.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, TypeScript 5, Tailwind CSS 4, Framer Motion |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0 async, Pydantic v2 |
| Queue | Redis + RQ |
| Database | PostgreSQL 16 |
| AI (primary) | Groq API — Llama 3.3 70B |
| AI (fallback) | Ollama — Qwen 2.5 7B (local CUDA) |

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (with Compose v2)
- Git

### 1. Clone & configure environment

```bash
git clone https://github.com/Sudalai-kumar/priva-search.git
cd priva-search

# Backend secrets
cp backend/.env.example backend/.env
# → Edit backend/.env and fill in GROQ_API_KEY and FIRECRAWL_API_KEY

# Frontend env (defaults work for local dev)
cp frontend.env.example frontend/.env.local
```

### 2. Start the stack

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Health check | http://localhost:8000/health |
| API Docs | http://localhost:8000/docs |

### 3. Stop

```bash
docker compose down
```

To also destroy data volumes:

```bash
docker compose down -v
```

---

## Project Structure

```
priva-search/
├── frontend/          # Next.js 15 application
├── backend/           # FastAPI application
├── docker-compose.yml
└── README.md
```

See `systemInstruction.md` for the full architecture reference.

---

## Development

### Backend only (without Docker)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend only (without Docker)

```bash
cd frontend
npm install
npm run dev
```

---

## Environment Variables

See `backend/.env.example` and `frontend.env.example` for all required variables.
