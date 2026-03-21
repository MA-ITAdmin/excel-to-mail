import json
import os
from pathlib import Path
from typing import Optional

import openpyxl
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_db, init_db
from email_service import render_template, send_email, split_emails

load_dotenv(Path(__file__).parent.parent / ".env")

app = FastAPI(title="OPR SendMail API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4321", "http://127.0.0.1:4321"],
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


def parse_excel(file_bytes: bytes) -> list[dict]:
    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
    ws = wb.active

    rows = []
    headers = None
    expected_cols = ["Sales", "Attn", "E-mail", "Email CC", "Attachment", "Email Subject", "Email Content"]

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c).strip() if c else "" for c in row]
            continue
        if all(c is None for c in row):
            continue
        record = {}
        for j, col in enumerate(expected_cols):
            if j < len(row):
                val = row[j]
                record[col] = str(val).strip() if val is not None else ""
            else:
                record[col] = ""
        rows.append(record)
    return rows


@app.post("/api/upload")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="請上傳 Excel 檔案 (.xlsx 或 .xls)")

    content = await file.read()
    try:
        rows = parse_excel(content)
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

    return {"session_id": session_id, "filename": file.filename, "rows": rows}


class SendRequest(BaseModel):
    session_id: int
    row_index: int
    send_type: str  # "test" or "official"
    test_email: Optional[str] = None


class SendAllRequest(BaseModel):
    session_id: int
    send_type: str  # "test" or "official"
    test_email: Optional[str] = None


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
    cfg = get_smtp_config()

    subject = render_template(row["Email Subject"], row)
    body = render_template(row["Email Content"], row)

    if req.send_type == "test":
        test_addr = req.test_email or os.getenv("TEST_EMAIL", cfg["from_addr"])
        to_addrs = [test_addr]
        cc_addrs = []
    else:
        to_addrs = split_emails(row["E-mail"])
        cc_addrs = split_emails(row["Email CC"])

    if not to_addrs:
        conn.execute(
            "INSERT INTO send_logs (session_id, row_index, send_type, to_email, subject, status, error) VALUES (?,?,?,?,?,?,?)",
            (req.session_id, req.row_index, req.send_type, "", subject, "error", "收件人為空"),
        )
        conn.commit()
        conn.close()
        raise HTTPException(status_code=400, detail="收件人 E-mail 為空")

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
            attachment_filename=row["Attachment"] or None,
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
    cfg = get_smtp_config()
    results = []

    for i, row in enumerate(rows):
        subject = render_template(row["Email Subject"], row)
        body = render_template(row["Email Content"], row)

        if req.send_type == "test":
            test_addr = req.test_email or os.getenv("TEST_EMAIL", cfg["from_addr"])
            to_addrs = [test_addr]
            cc_addrs = []
        else:
            to_addrs = split_emails(row["E-mail"])
            cc_addrs = split_emails(row["Email CC"])

        if not to_addrs:
            results.append({"row": i, "status": "error", "error": "收件人為空"})
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
                attachment_filename=row["Attachment"] or None,
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
