"""Account helpers: who is "alice@x.com" / "+91 98765 43210" / "admin", password-reset codes, delivery, rate limits.

One account can carry an email, a phone number and a username; any of them signs in. Accounts created with a
phone only get a hidden placeholder address (…@phone.invalid, a reserved domain that can never receive mail).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import smtplib
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from .config import get_settings
from .models import PasswordReset, User

log = logging.getLogger("smriti.accounts")
PLACEHOLDER_DOMAIN = "phone.invalid"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[a-z][a-z0-9_.]{2,29}$")


# ---------------- identifiers ----------------

def normalize_phone(raw: str) -> str | None:
    """'+91 98765-43210', '09876543210', '9876543210' -> '+919876543210'. Ten-digit numbers are taken as Indian."""
    s = raw.strip()
    digits = re.sub(r"\D", "", s)
    if s.startswith("+"):
        return f"+{digits}" if 8 <= len(digits) <= 15 else None
    if s.startswith("00") and 10 <= len(digits) - 2 <= 15:
        return f"+{digits[2:]}"
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10 and digits[0] in "6789":
        return f"+91{digits}"
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    return None


def kind_of(identifier: str) -> str:
    s = identifier.strip()
    if "@" in s:
        return "email"
    if normalize_phone(s):
        return "phone"
    return "username"


def find_user(db: Session, identifier: str) -> User | None:
    s = identifier.strip()
    k = kind_of(s)
    if k == "email":
        return db.query(User).filter(func.lower(User.email) == s.lower()).first()
    if k == "phone":
        return db.query(User).filter(User.phone == normalize_phone(s)).first()
    return db.query(User).filter(func.lower(User.username) == s.lower()).first()


def placeholder_email(phone: str) -> str:
    return f"{phone.lstrip('+')}@{PLACEHOLDER_DOMAIN}"


def real_email(u: User) -> str | None:
    return None if (u.email or "").endswith(".invalid") else u.email  # placeholders use the reserved .invalid domain


def mask(value: str) -> str:
    if "@" in value:
        name, dom = value.split("@", 1)
        return f"{name[:2]}{'•' * max(1, len(name) - 2)}@{dom}"
    return f"{value[:3]}{'•' * max(1, len(value) - 5)}{value[-2:]}"


def check_password_strength(pw: str) -> None:
    if len(pw) < 8:
        raise HTTPException(422, "Use a password of at least 8 characters.")
    if pw.isdigit() or pw.lower() in {"password", "password1", "12345678", "qwertyui"}:
        raise HTTPException(422, "That password is too easy to guess. Mix letters and numbers.")


# ---------------- rate limiting (in memory, per process) ----------------

_hits: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def limited(key: str, max_hits: int, window_s: int) -> bool:
    """Record one attempt; True when `key` has gone over `max_hits` within `window_s` seconds."""
    now = time.time()
    with _lock:
        hits = [t for t in _hits[key] if now - t < window_s]
        hits.append(now)
        _hits[key] = hits
        return len(hits) > max_hits


def clear_limit(key: str) -> None:
    with _lock:
        _hits.pop(key, None)


# ---------------- delivery ----------------

def email_ready() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from)


def send_email(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not email_ready():
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_tls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:
        log.exception("could not send email to %s", mask(to))
        return False


# ---------------- reset codes ----------------

def _hash_code(code: str) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def issue_reset(db: Session, u: User, via: str) -> tuple[str, str | None]:
    """Create a 6-digit, single-use, 15-minute code and send it. Returns (channel used, masked destination)."""
    db.query(PasswordReset).filter(PasswordReset.user_id == u.id, PasswordReset.used.is_(False)).update({"used": True})
    code = f"{secrets.randbelow(10**6):06d}"
    db.add(PasswordReset(user_id=u.id, code_hash=_hash_code(code), expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)))
    db.commit()
    text = f"Your Smriti password reset code is {code}. It expires in 15 minutes. If you didn't ask for this, ignore this message."
    email, phone = real_email(u), u.phone
    if email and send_email(email, "Your Smriti reset code", text):
        return "email", mask(email)
    # No mail service configured (text-message OTP comes later): the owner can read the code from the log.
    log.warning("PASSWORD RESET CODE for %s: %s (no email service configured; set SMTP_* in .env)",
                mask(email or phone or u.username or u.id), code)
    return "log", None


def consume_reset(db: Session, u: User, code: str) -> bool:
    now = datetime.now(timezone.utc)
    r = (db.query(PasswordReset).filter(PasswordReset.user_id == u.id, PasswordReset.used.is_(False))
         .order_by(PasswordReset.created_at.desc()).first())
    if not r:
        return False
    exp = r.expires_at if r.expires_at.tzinfo else r.expires_at.replace(tzinfo=timezone.utc)
    if exp < now or r.attempts >= 5:
        r.used = True
        db.commit()
        return False
    if not hmac.compare_digest(r.code_hash, _hash_code(code.strip())):
        r.attempts += 1
        db.commit()
        return False
    r.used = True
    db.commit()
    return True


# ---------------- the owner account ----------------

def ensure_admin_account() -> None:
    """Create the 'admin' account once, with a random one-time password written to data/admin-credentials.txt.

    The password must be changed at first sign-in; the file is removed by then (see /me/password)."""
    from .db import SessionLocal
    from .security import hash_password
    s = get_settings()
    db = SessionLocal()
    try:
        if db.query(User).filter(func.lower(User.username) == s.admin_username.lower()).first():
            return
        pw = secrets.token_urlsafe(9)
        db.add(User(email=f"{s.admin_username}@admin.invalid", username=s.admin_username, hashed_password=hash_password(pw),
                    display_name="Administrator", is_admin=True, must_change_password=True))
        db.commit()
        path = s.data_path / "admin-credentials.txt"
        path.write_text(f"Smriti administrator\nusername: {s.admin_username}\none-time password: {pw}\n\n"
                        "Sign in with these, then choose your own password (you'll be asked straight away).\n"
                        "This file is deleted automatically once you do.\n", encoding="utf-8")
        log.warning("Created the '%s' account. Its one-time password is in %s", s.admin_username, path.resolve())
    finally:
        db.close()
