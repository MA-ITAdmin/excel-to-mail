import json
import os
import re
from pathlib import Path

import openpyxl
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database import get_db, init_db
from email_service import render_template, send_email, split_emails

ATTACHMENTS_BASE_DIR = Path(__file__).parent.parent / "attachments"
EXAMPLE_FILE = Path(__file__).parent.parent / "example.xlsx"


def get_session_dir(session_id: int) -> Path:
    return ATTACHMENTS_BASE_DIR / str(session_id)

load_dotenv(Path(__file__).parent.parent / ".env")

app = FastAPI(title="批次郵件發送 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://127.0.0.1:4321", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


def get_smtp_config():
    return {
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": os.getenv("SMTP_USER", ""),
        "smtp_pass": os.getenv("SMTP_PASS", ""),
        "smtp_tls": os.getenv("SMTP_TLS", "true").lower() == "true",
        "from_addr": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
    }


def get_mailpit_config():
    return {
        "smtp_host": os.getenv("MAILPIT_HOST", "localhost"),
        "smtp_port": int(os.getenv("MAILPIT_PORT", "1025")),
        "smtp_user": "",
        "smtp_pass": "",
        "smtp_tls": False,
        "from_addr": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
    }


EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

EXPECTED_COLS = ["Sales", "Attn", "E-mail", "Email CC", "Attachment", "Email Subject", "Email Content"]
REQUIRED_COLS = ["E-mail", "Email Subject", "Email Content"]


def validate_row(row: dict) -> list[str]:
    errors = []
    for col in REQUIRED_COLS:
        if not row.get(col, "").strip():
            errors.append(f"{col} 不可為空")
    for field in ["E-mail", "Email CC"]:
        val = row.get(field, "").strip()
        if not val:
            continue
        from email_service import split_emails
        for addr in split_emails(val):
            if not EMAIL_RE.match(addr):
                errors.append(f"{field} 格式錯誤：{addr}")
    return errors


def eval_concat(expr: str, row_values: list) -> str:
    """Evaluate Excel-style string concatenation: "text"&B2&"text" """
    parts = re.split(r"&", expr)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Quoted string literal "..."
        m = re.match(r'^"(.*)"$', part, re.DOTALL)
        if m:
            result.append(m.group(1))
            continue
        # Cell reference like A2, B2, G10
        m = re.match(r"^([A-Z]+)(\d+)$", part, re.IGNORECASE)
        if m:
            col_idx = ord(m.group(1).upper()[0]) - ord("A")
            if 0 <= col_idx < len(row_values):
                val = row_values[col_idx]
                result.append(str(val) if val is not None else "")
            continue
        result.append(part)
    return "".join(result)


def resolve_cell(value, row_values: list) -> str:
    """Return final string value for a cell, evaluating Excel formulas if needed."""
    if value is None:
        return ""
    val_str = str(value).strip()
    if not val_str:
        return ""
    # Actual formula starting with =
    if val_str.startswith("="):
        return eval_concat(val_str[1:], row_values)
    # Formula-like text without = (e.g., cached value wasn't saved):  "text"&B2&"text"
    if "&" in val_str and re.search(r"\b[A-Z]\d+\b", val_str):
        return eval_concat(val_str, row_values)
    return val_str


def parse_excel(file_bytes: bytes) -> tuple[list[dict], list[list[str]]]:
    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=False)
    ws = wb.active

    all_rows = list(ws.iter_rows(values_only=False))
    if not all_rows:
        return [], []

    # Validate and map headers by name
    header = [str(cell.value).strip() if cell.value else "" for cell in all_rows[0]]
    missing = [col for col in EXPECTED_COLS if col not in header]
    if missing:
        raise ValueError(f"Excel 缺少欄位：{', '.join(missing)}")
    col_map = {col: header.index(col) for col in EXPECTED_COLS}

    rows, row_errors = [], []
    for row in all_rows[1:]:
        raw_values = [cell.value for cell in row]
        if all(v is None for v in raw_values):
            continue
        record = {}
        for col in EXPECTED_COLS:
            idx = col_map[col]
            cell_val = raw_values[idx] if idx < len(raw_values) else None
            record[col] = resolve_cell(cell_val, raw_values)
        rows.append(record)
        row_errors.append(validate_row(record))
    return rows, row_errors


@app.get("/api/attachments/{session_id}")
def list_attachments(session_id: int):
    session_dir = get_session_dir(session_id)
    if not session_dir.exists():
        return {"files": []}
    files = [f.name for f in session_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
    return {"files": sorted(files)}


@app.post("/api/attachments/{session_id}")
async def upload_attachments(session_id: int, files: list[UploadFile] = File(...)):
    session_dir = get_session_dir(session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for file in files:
        dest = session_dir / file.filename
        content = await file.read()
        dest.write_bytes(content)
        saved.append(file.filename)
    return {"saved": saved}


@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="請上傳 Excel 檔案 (.xlsx 或 .xls)")

    content = await file.read()
    try:
        rows, row_errors = parse_excel(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"解析 Excel 失敗: {str(e)}")

    if not rows:
        raise HTTPException(status_code=400, detail="Excel 檔案沒有資料")

    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO upload_sessions (filename, row_count, data) VALUES (?, ?, ?)",
        (file.filename, len(rows), json.dumps(rows, ensure_ascii=False)),
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {"session_id": session_id, "filename": file.filename, "rows": rows, "row_errors": row_errors}


class SendRequest(BaseModel):
    session_id: int
    row_index: int
    send_type: str  # "test" or "official"


class SendAllRequest(BaseModel):
    session_id: int
    send_type: str  # "test" or "official"


@app.post("/api/send")
def send_one(req: SendRequest):
    conn = get_db()
    row_data = conn.execute(
        "SELECT data FROM upload_sessions WHERE id = ?", (req.session_id,)
    ).fetchone()
    if not row_data:
        raise HTTPException(status_code=404, detail="Session 不存在")

    rows = json.loads(row_data["data"])
    if req.row_index >= len(rows):
        raise HTTPException(status_code=400, detail="row_index 超出範圍")

    row = rows[req.row_index]
    cfg = get_mailpit_config() if req.send_type == "test" else get_smtp_config()

    subject = render_template(row["Email Subject"], row)
    body = render_template(row["Email Content"], row)

    to_addrs = split_emails(row["E-mail"])
    cc_addrs = split_emails(row["Email CC"]) if req.send_type != "test" else []

    if not to_addrs:
        conn.execute(
            "INSERT INTO send_logs (session_id, row_index, send_type, to_email, subject, status, error) VALUES (?,?,?,?,?,?,?)",
            (req.session_id, req.row_index, req.send_type, "", subject, "error", "收件人為空"),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=400, detail="收件人 E-mail 為空")

    attachment_filename = row["Attachment"] or None
    attachment_path = (get_session_dir(req.session_id) / attachment_filename) if attachment_filename else None
    if attachment_path and not attachment_path.exists():
        conn.execute(
            "INSERT INTO send_logs (session_id, row_index, send_type, to_email, subject, status, error) VALUES (?,?,?,?,?,?,?)",
            (req.session_id, req.row_index, req.send_type, ",".join(to_addrs), subject, "error", f"找不到附件：{attachment_filename}"),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=400, detail=f"找不到附件：{attachment_filename}")

    try:
        send_email(
            smtp_host=cfg["smtp_host"],
            smtp_port=cfg["smtp_port"],
            smtp_user=cfg["smtp_user"],
            smtp_pass=cfg["smtp_pass"],
            smtp_tls=cfg["smtp_tls"],
            from_addr=cfg["from_addr"],
            to_addrs=to_addrs,
            cc_addrs=cc_addrs,
            subject=subject,
            body=body,
            attachment_path=attachment_path,
        )
        status = "success"
        error = None
    except Exception as e:
        status = "error"
        error = str(e)

    conn.execute(
        "INSERT INTO send_logs (session_id, row_index, send_type, to_email, cc_email, subject, status, error) VALUES (?,?,?,?,?,?,?,?)",
        (req.session_id, req.row_index, req.send_type, ",".join(to_addrs), ",".join(cc_addrs), subject, status, error),
    )
    conn.commit()
    conn.close()

    if status == "error":
        raise HTTPException(status_code=500, detail=f"寄送失敗: {error}")

    return {"status": "success", "to": to_addrs, "cc": cc_addrs, "subject": subject}


@app.post("/api/send-all")
def send_all(req: SendAllRequest):
    conn = get_db()
    row_data = conn.execute(
        "SELECT data FROM upload_sessions WHERE id = ?", (req.session_id,)
    ).fetchone()
    if not row_data:
        raise HTTPException(status_code=404, detail="Session 不存在")

    rows = json.loads(row_data["data"])
    cfg = get_mailpit_config() if req.send_type == "test" else get_smtp_config()
    results = []

    for i, row in enumerate(rows):
        subject = render_template(row["Email Subject"], row)
        body = render_template(row["Email Content"], row)

        to_addrs = split_emails(row["E-mail"])
        cc_addrs = split_emails(row["Email CC"]) if req.send_type != "test" else []

        if not to_addrs:
            results.append({"row": i, "status": "error", "error": "收件人為空"})
            continue

        attachment_filename = row["Attachment"] or None
        attachment_path = (get_session_dir(req.session_id) / attachment_filename) if attachment_filename else None
        if attachment_path and not attachment_path.exists():
            err_msg = f"找不到附件：{attachment_filename}"
            conn.execute(
                "INSERT INTO send_logs (session_id, row_index, send_type, to_email, cc_email, subject, status, error) VALUES (?,?,?,?,?,?,?,?)",
                (req.session_id, i, req.send_type, ",".join(to_addrs), ",".join(cc_addrs), subject, "error", err_msg),
            )
            results.append({"row": i, "status": "error", "error": err_msg})
            continue

        try:
            send_email(
                smtp_host=cfg["smtp_host"],
                smtp_port=cfg["smtp_port"],
                smtp_user=cfg["smtp_user"],
                smtp_pass=cfg["smtp_pass"],
                smtp_tls=cfg["smtp_tls"],
                from_addr=cfg["from_addr"],
                to_addrs=to_addrs,
                cc_addrs=cc_addrs,
                subject=subject,
                body=body,
                attachment_path=attachment_path,
            )
            status = "success"
            error = None
        except Exception as e:
            status = "error"
            error = str(e)

        conn.execute(
            "INSERT INTO send_logs (session_id, row_index, send_type, to_email, cc_email, subject, status, error) VALUES (?,?,?,?,?,?,?,?)",
            (req.session_id, i, req.send_type, ",".join(to_addrs), ",".join(cc_addrs), subject, status, error),
        )
        results.append({"row": i, "status": status, "error": error, "to": to_addrs})

    conn.commit()
    conn.close()
    return {"results": results}


@app.get("/api/logs/{session_id}")
def get_logs(session_id: int):
    conn = get_db()
    logs = conn.execute(
        "SELECT * FROM send_logs WHERE session_id = ? ORDER BY id DESC",
        (session_id,),
    ).fetchall()
    conn.close()
    return {"logs": [dict(r) for r in logs]}


@app.get("/api/config")
def get_config():
    """Return non-sensitive config info."""
    return {
        "smtp_host": os.getenv("SMTP_HOST", ""),
        "smtp_from": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
        "test_email": os.getenv("TEST_EMAIL", ""),
    }


@app.get("/api/example")
def download_example():
    if not EXAMPLE_FILE.exists():
        raise HTTPException(status_code=404, detail="範例檔案不存在")
    return FileResponse(
        path=EXAMPLE_FILE,
        filename="example.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
