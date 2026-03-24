import smtplib
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional
import os


def split_emails(raw: str) -> list[str]:
    """Split email string by ; or , and strip whitespace."""
    if not raw or not raw.strip():
        return []
    parts = re.split(r"[;,]", raw)
    return [p.strip() for p in parts if p.strip()]


def render_template(template: str, row: dict) -> str:
    """Replace {Sales} and {Attn} placeholders with row values."""
    result = template
    for key, value in row.items():
        result = result.replace(f"{{{key}}}", str(value) if value else "")
    return result


def send_email(
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    smtp_tls: bool,
    from_addr: str,
    to_addrs: list[str],
    cc_addrs: list[str],
    subject: str,
    body: str,
    attachment_path: Optional[Path] = None,
    bcc_addrs: list[str] = None,
) -> None:
    bcc_addrs = bcc_addrs or []
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    if cc_addrs:
        msg["Cc"] = ", ".join(cc_addrs)
    if bcc_addrs:
        msg["Bcc"] = ", ".join(bcc_addrs)
    msg["Subject"] = subject

    # Support HTML content
    if "<" in body and ">" in body:
        msg.attach(MIMEText(body, "html", "utf-8"))
    else:
        # Convert newlines to <br> for plain text
        msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path and attachment_path.exists():
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{attachment_path.name}"',
        )
        msg.attach(part)

    all_recipients = to_addrs + cc_addrs + bcc_addrs

    # smtp_tls="starttls" → SMTP + STARTTLS
    # smtp_tls="ssl"      → SMTP_SSL
    # smtp_tls=False/""   → plain SMTP (internal relay)
    smtp_mode = os.getenv("SMTP_MODE", "").lower()
    if smtp_mode == "ssl":
        server = smtplib.SMTP_SSL(smtp_host, smtp_port)
    elif smtp_tls or smtp_mode == "starttls":
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP(smtp_host, smtp_port)

    if smtp_user and smtp_pass:
        server.login(smtp_user, smtp_pass)

    server.sendmail(from_addr, all_recipients, msg.as_string())
    server.quit()
