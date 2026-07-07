# AI-Powered Role-Based Candidate Screening System

A RAG-based technical interview system: a candidate uploads a resume, picks a role,
and the system generates interview questions grounded in a role-specific textbook
knowledge base, adapting to the candidate's background and previous answers.

## Architecture

```
React (Vite)  --->  FastAPI  --->  Groq (LLM)          [generation: extraction, queries, questions, summary]
                       |
                       ---------->  ChromaDB (vector store) [role-specific book chunks, retrieval only]
                       |
                       ---------->  SQLite (SQLAlchemy)  [sessions, questions, answers, reports]
```

**Flow per interview:**

1. Candidate uploads resume + picks role → backend extracts raw text (PyPDF2/pypdf)
2. Groq extracts structured `skills / technologies / domains` from the resume text
3. Groq turns that + the role into 2-3 short retrieval queries
4. Those queries are embedded and searched against the **role-specific** Chroma
   collection (books for that role only — never cross-role)
5. Retrieved textbook chunks + resume context + interview history → Groq generates
   one grounded, non-generic interview question
6. Candidate answers → stored in SQLite → steps 3-5 repeat (previous Q&A pairs are
   fed back in, so difficulty adapts to how the candidate is doing)
7. After `MAX_QUESTIONS` (default 5) → Groq generates a structured summary from the
   full transcript

## Key design decisions

- **One Chroma collection per role** (`role_ai_ml`, `role_data_science`, ...) rather
  than one shared collection with a metadata filter. This makes cross-role leakage
  structurally impossible rather than something enforced only by query-time filtering.
- **Ingestion is a separate, offline, idempotent script** (`scripts/ingest_books.py`),
  never run inside a request. The running API only ever *reads* from the pre-built
  Chroma store. Re-running the script safely wipes and rebuilds a role's collection.
- **Word-count chunking with overlap** (250 words, 40-word overlap) instead of naive
  fixed-character splitting — simple to reason about, and overlap prevents a concept
  from being cut across a chunk boundary.
- **The resume is never embedded or stored in the vector DB.** It only drives what
  queries get generated. The vector DB holds book knowledge only; SQLite holds
  session/answer data only. Keeping these separate keeps the system's mental model
  simple to explain and debug.
- **SQLite + SQLAlchemy** for persistence — sufficient for this scope, and the ORM
  layer means swapping to Postgres later is a one-line connection-string change.
- **Local sentence-transformers embeddings** (`all-MiniLM-L6-v2`, via Chroma) instead
  of a paid embedding API — free, fast enough for a small corpus, and keeps Groq
  calls reserved for generation tasks only (cheaper + faster on the LLM side).
- **Adaptive difficulty is prompt-based, not a separate model**: each question
  generation call receives the full previous Q&A history and is instructed to go
  deeper on strong answers or stay foundational after weak ones.
- **Traceability**: every generated question stores the retrieved chunks that
  produced it (`source_chunks_json`), and the frontend has a collapsible "Show
  retrieved context" panel per question so you can see exactly which textbook
  passage grounded that question.

## Project structure

```
backend/
  app/
    main.py              # FastAPI app, CORS, router mounting
    config.py             # env-driven settings, supported roles
    database.py           # SQLAlchemy engine/session
    models.py              # InterviewSession, QAPair ORM models
    schemas.py              # Pydantic request/response models
    chunking.py              # text cleaning + word-count chunking
    vector_store.py           # Chroma wrapper: add/query, one collection per role
    llm.py                     # all Groq prompts live here (single source of truth)
    resume_parser.py            # PDF/TXT -> raw text
    routers/interview.py          # /api/roles, /api/interview/start, /answer, /summary
  scripts/ingest_books.py          # one-time offline ingestion script
  data/books/<role>/*.pdf|*.txt     # source books per role (sample corpus included)
  requirements.txt
  .env.example

frontend/
  src/
    App.jsx                # upload -> interview -> summary flow
    api.js                   # fetch wrapper for backend calls
    App.css                    # styling
  package.json
```

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GROQ_API_KEY (free key: https://console.groq.com/keys)
```

**Add your knowledge base.** A small sample corpus is already included under
`data/books/ai_ml/` and `data/books/data_science/` so the system runs out of the box.
To use the actual assignment books, drop the PDFs into the matching role folder
(e.g. `data/books/ai_ml/mitchell_ml.pdf`), then re-run ingestion:

```bash
python scripts/ingest_books.py
```

This is safe to re-run any time you add/change books — it rebuilds that role's
collection from scratch.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Docs available at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. It talks to the backend at `http://localhost:8000`
(hardcoded in `src/api.js` — change `BASE_URL` there if you deploy the backend
elsewhere).

## Adding a new role

1. Create `backend/data/books/<new_role>/` and drop in PDFs/TXTs
2. Add `<new_role>` to `SUPPORTED_ROLES` and `ROLE_DISPLAY_NAMES` in `app/config.py`
3. Run `python scripts/ingest_books.py`

## Notes / known limitations

- `MAX_QUESTIONS` is fixed per session (default 5) — configurable via `.env`
- Embeddings download a small model (~90MB) from Hugging Face on first run; this
  requires internet access the first time only, then it's cached locally
- CORS is wide open (`allow_origins=["*"]`) for local demo convenience — restrict
  this before any real deployment
- No auth — sessions are only protected by an unguessable UUID; add auth if this
  were to handle real candidate data
