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

## Sign in with Google

Optional. The "Continue with Google" button (and One Tap) appears once a client ID is set:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an **OAuth client ID** of type **Web application**.
2. Under **Authorized JavaScript origins**, add every address people open Smriti from (for example `http://localhost:3000`). No redirect URI is needed.
3. Put the client ID in `backend/.env` as `GOOGLE_CLIENT_ID=…` and restart the backend.

The backend checks each Google sign-in with Google: it must be meant for this app and the email must be verified. A Google account whose email matches an existing account is linked to it, so both ways of signing in open the same library.

## Asking for a specific file

Requests like "share my pan card", "rahul's abha card", "मेरा आधार कार्ड भेजो" or "share the beach photo I took in Goa" return that file with Share / Download buttons and an honest note on anything that could not be confirmed (an unreadable name, a photo without location data).

- **What a file is** comes from `backend/app/understanding/doc_types.py`: a data registry (PAN, Aadhaar, ABHA, voter ID, passport, driving licence, invoices, tickets, certificates, signature, ...) scored from OCR text, ID-number patterns (Aadhaar checksum included), filename words and visual cues. Add types there, or list extra ones in a JSON file and set `DOC_TYPES_FILE`.
- **Whose it is** comes from the name printed on the card (`entities.py`); "my ..." prefers files that carry your display name.
- **Visual cues** (`visual.py`) recognise signatures and scenes such as beach/sea, greenery, snow and sunset offline.
- **File formats** are detected from content, so `.jfif`, WebP saved as `.jpeg`, HEIC, AVIF and the like all work.
- OCR needs Tesseract. On Windows, `winget install UB-Mannheim.TesseractOCR` works as is; it's found in Program Files automatically (or set `TESSERACT_CMD`). After upgrading, use **Settings → Reprocess all files**.

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
