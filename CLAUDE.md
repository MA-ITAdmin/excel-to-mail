# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OPR SendMail is a bulk email sender that reads recipient data from an Excel file and sends personalized emails with PDF attachments. It has a FastAPI backend and an Astro frontend (single-page, no framework components).

## Running the App

**Backend** (from repo root):
```bash
source venv/bin/activate
cd backend
uvicorn main:app --reload
# Runs at http://localhost:8000
```

**Frontend** (from `frontend/`):
```bash
npm run dev
# Runs at http://localhost:4321
```

## Environment Setup

Copy `.env.example` to `.env` at the repo root and fill in SMTP credentials. The backend reads `.env` from the parent directory of `backend/`.

Key env vars:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_TLS`
- `SMTP_MODE`: `starttls` (default), `ssl`, or empty for plain SMTP
- `TEST_EMAIL`: default recipient for test sends

## Architecture

```
/
├── backend/
│   ├── main.py          # FastAPI app, all API routes, Excel parsing
│   ├── email_service.py # SMTP send logic, template rendering
│   └── database.py      # SQLite via raw sqlite3 (data/sendmail.db)
├── attachments/         # PDF files referenced by Excel rows
├── frontend/
│   └── src/pages/index.astro  # Entire UI — single file, vanilla JS
└── .env                 # SMTP config (not committed)
```

**Data flow:**
1. User uploads Excel → `POST /api/upload` parses it and stores as JSON in SQLite `upload_sessions` table, returns `session_id`
2. Frontend sends per-row or bulk send requests → `POST /api/send` or `POST /api/send-all`
3. Backend renders `{Sales}`, `{Attn}`, etc. placeholders in subject/body, looks up attachment by filename in `attachments/`, sends via SMTP
4. All send attempts logged to `send_logs` table

**Excel format** (required columns in order): `Sales`, `Attn`, `E-mail`, `Email CC`, `Attachment`, `Email Subject`, `Email Content`

The backend handles Excel formulas — `resolve_cell()` in `main.py` evaluates `=` formulas and `"text"&B2` style concatenations using `eval_concat()`.

**Test vs Official send:** Test mode redirects all emails to the `test_email` address (from UI field or `TEST_EMAIL` env var), ignoring the Excel `E-mail` column.

## Dependencies

Backend: `fastapi`, `uvicorn`, `openpyxl`, `python-multipart`, `python-dotenv` (see `requirements.txt`)

Frontend: Astro 6 with no framework components; all logic is vanilla JS in `index.astro`

The frontend JS hardcodes `const API = 'http://localhost:8000'` — change this for production.
