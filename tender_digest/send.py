"""Send mail through Gmail SMTP with an app password.

Needs GMAIL_USER (the sending Gmail address), GMAIL_APP_PASSWORD and DIGEST_TO
(comma-separated recipients). Gmail authenticates as the mailbox, so the From address
is always GMAIL_USER.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage


class SendError(RuntimeError):
    pass


def configured() -> bool:
    return all(os.environ.get(k) for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "DIGEST_TO"))


def send(subject: str, text: str, html: str | None = None) -> list[str]:
    user = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "")
    to = [a.strip() for a in os.environ.get("DIGEST_TO", "").split(",") if a.strip()]
    if not (user and password and to):
        raise SendError("GMAIL_USER, GMAIL_APP_PASSWORD and DIGEST_TO must all be set")

    msg = EmailMessage()
    msg["From"] = f"Tender digest <{user}>"
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=60) as s:
            s.starttls(context=ssl.create_default_context())
            s.login(user, password)
            s.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        raise SendError(f"Gmail SMTP send failed: {exc!r}") from exc
    return to
