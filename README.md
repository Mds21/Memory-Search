# Smriti — personal memory & document search

Search your photos, videos and documents by describing them, in English, Hindi, Marathi, Tamil or Spanish. Ask questions about your documents and get answers with citations. Everything runs locally and offline by default; paid or heavier models plug in later through environment variables.

```
smriti/
├── backend/    FastAPI service (REST + SSE), SQLite, in-process workers   → :8000
├── frontend/   Next.js 14 + Tailwind UI (separate service)                → :3000
├── docs/       Statement of Work (.docx) and agent-readable technical spec
└── docker-compose.yml
```

The two services talk only over HTTP (`NEXT_PUBLIC_API_URL`), so they can live in separate repos, containers or hosts.

## Quick start

**Docker (everything):**
```bash
docker compose up --build
# UI  http://localhost:3000     API docs  http://localhost:8000/docs
```
The first account you register becomes the admin.

**Without Docker:**
```bash
# backend (Python 3.12; needs ffmpeg, poppler-utils and tesseract-ocr for video/PDF/OCR)
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --reload --port 8000

# frontend (Node 20)
cd frontend && cp .env.example .env.local && npm install && npm run dev
```

## What works

| Area | Features |
|---|---|
| Ingest | Photos, videos, PDF/Word/PowerPoint/Excel/text, ZIP import, drag-and-drop anywhere, de-duplication, progress and retry, thumbnails appear before indexing finishes |
| Search | Natural-language chat; hybrid dense + keyword + metadata ranking with rank fusion; dates ("last December"), places, kinds and tags parsed from the query in 5 languages; follow-ups ("only videos"); editable filter chips |
| Answers | Streaming answers with `[S1]` citations that open the exact page or video moment |
| Browse | Library with bulk select, timeline histogram, map clusters, collections, on-this-day, saved searches, similar items |
| Edit | Caption, tags, place and date, searchable immediately |
| Account | JWT auth, per-user isolation, data export, full account deletion |
| UI | Responsive, keyboard friendly (`/` focuses search, arrows and Esc in the viewer), 5 UI languages. Voice button is present but disabled (Phase 2) |

## Swapping in better models (no code changes)

Edit `backend/.env`, then restart. Re-process files from Settings to re-embed with a new model.

| Setting | Offline default | Upgrade |
|---|---|---|
| `TEXT_EMBEDDER` | `hash` | `ollama:bge-m3` or `st:BAAI/bge-m3` (real multilingual semantics) |
| `IMAGE_EMBEDDER` | `none` | `openclip` (text → image search) |
| `VLM` | `basic` | `ollama:qwen2.5vl:3b` (real photo captions) |
| `LLM` | `extractive` | `ollama:qwen2.5:3b` (written answers) |
| `STT` | `none` | `faster_whisper:small` (video transcripts) |

`docker compose --profile ai up` starts an Ollama container; pull the models with `docker compose exec ollama ollama pull bge-m3`.

## Honest limits of this build

- **Photo search quality depends on the VLM/CLIP adapters.** With the offline defaults, photos are found by date, place (EXIF GPS), filename, OCR text, colour/tone heuristics and anything you caption or tag. Enable Ollama and OpenCLIP for real semantic photo search.
- The Ollama, sentence-transformers, OpenCLIP and Whisper adapters are written against the adapter interfaces but were **not run** in the build environment (no model downloads). Everything else is covered by the backend test suite and a live smoke test.
- Storage is SQLite plus local disk, with the same adapter seams the spec describes for Postgres/pgvector and S3/MinIO. Fine for one person or a small group; swap before multi-user production.
- Map tiles come from OpenStreetMap's public server. Use your own tile provider for production traffic.
- Tesseract languages are limited to those installed (the Docker image adds English, Hindi, Marathi, Tamil, Spanish).

## Tests

```bash
cd backend && pytest        # 23 tests: auth, ingest, OCR, filters, RAG citations, isolation, deletion, signed URLs
cd frontend && npx tsc --noEmit && npm run build
```

## Docs

- `docs/Statement_of_Work.docx` — scope, deliverables, timeline, acceptance
- `docs/Technical_Spec_for_Agents.md` — architecture, data model, API and build contract
