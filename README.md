# Lawyer AI — case prep assistant

Upload the files of one criminal case (notes, PDFs, scanned statements, evidence photos). The app:

- finds contradictions between testimonies and evidence, and weak or missing evidence,
- prepares arguments and counter-arguments, each cited to the exact page or image region,
- runs a mock trial where you argue against an AI judge, public prosecutor, investigating officer and witnesses.

Each case is stored in its own isolated folder and database. Models can run locally (Ollama) or in the cloud, chosen per role.

Status: Stages 0–3 done (foundation, sample data, upload + OCR + search + viewer, model routing + tracing). Two synthetic test cases with answer keys and scripted mock-trial rounds are in [samples/](samples/): upload the files in `samples/<case>/files/`. See [docs/plan.md](docs/plan.md) for the staged build plan.

## Run locally

Requirements: Python 3.13 + [uv](https://docs.astral.sh/uv/), Node 22, Docker (for tracing), [Ollama](https://ollama.com) for local models.

```bash
cp .env.example .env            # add a cloud API key if you use the hybrid/cloud profile
ollama pull qwen3.5:4b && ollama pull nomic-embed-text
docker run -d --name lawyer-ai-phoenix -p 6006:6006 arizephoenix/phoenix
cd backend && uv sync && uv run uvicorn app.main:app --reload --reload-dir app --port 8010
cd frontend && npm install && npm run dev      # http://localhost:5173
```

Traces: http://localhost:6006

## Test

```bash
cd backend && uv run ruff check . && uv run pyright && uv run pytest
cd frontend && npm run lint && npm run build
```

## Later (not built yet)
Multi-user accounts and roles, encryption at rest, voice, statute and case-law search, DMS integration, E2E browser tests.
