# ProblemFinder

A problem-discovery engine that collects real-world problems from curated sources,
uses a local LLM (Ollama) to assess the best collection method for each source and to
enrich problems with analysis (frequency, existing solutions, pricing, and recommended
tech stacks), and presents everything in a React UI.

- **Backend:** FastAPI (async SQLAlchemy 2.0) + PostgreSQL + Alembic, with Ollama for AI
  and Crawlee/Playwright for JavaScript-aware scraping.
- **Frontend:** React 19 + Vite + TypeScript + React Router.

## Architecture

```
frontend (Vite :5173)  ->  backend (FastAPI :8000)  ->  PostgreSQL :5432
                                          |
                                          +---------->  Ollama :11434 (local LLM)
```

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- PostgreSQL 14+
- [Ollama](https://ollama.com) (for the AI assessment / enrichment features)

## Setup

### 1. PostgreSQL

Create a database and user (defaults used below match `backend/.env.example`):

```bash
sudo -u postgres psql -c "CREATE USER problemfinder WITH PASSWORD 'problemfinder';"
sudo -u postgres psql -c "CREATE DATABASE problemfinder OWNER problemfinder;"
```

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env        # edit if your DB credentials differ

# Apply database migrations
alembic upgrade head

# Seed the initial data sources (14 sources)
python -m app.scripts.seed_script

# Run the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Ollama (AI features)

```bash
# Install: https://ollama.com/download
ollama serve            # start the server (http://localhost:11434)
ollama pull llama3.2:1b # pull the model referenced by OLLAMA_MODEL
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173
```

Open http://localhost:5173. The Sources page lists the seeded sources; click **Assess**
to have the AI classify a source's collection method (API / Web Scraping / Manual), then
**Fetch** to collect and AI-enrich problems, viewable on the **Discovered Problems** page.

## Key API endpoints

- `GET  /health` — service + database health check
- `GET  /api/sources/` — list sources
- `POST /api/sources/{source_id}/assess` — AI-assess a single source
- `POST /api/sources/assess-all` — assess all pending sources
- `POST /api/source-items/{source_id}/fetch` — collect + enrich problems for a source
- `GET  /api/source-items/` — list collected problems
- `POST /ai/test` — quick Ollama connectivity check
