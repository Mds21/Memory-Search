import base64
import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User

_ph = PasswordHasher()
_ALG = "HS256"


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except VerifyMismatchError:
        return False


def _token(sub: str, kind: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": sub, "typ": kind, "iat": now, "exp": now + ttl}, get_settings().jwt_secret, algorithm=_ALG)


def make_tokens(user_id: str) -> dict:
    s = get_settings()
    return {
        "access_token": _token(user_id, "access", timedelta(minutes=s.access_ttl_min)),
        "refresh_token": _token(user_id, "refresh", timedelta(days=s.refresh_ttl_days)),
        "token_type": "bearer",
        "expires_in": s.access_ttl_min * 60,
    }


def decode(token: str, kind: str) -> str:
    try:
        d = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    if d.get("typ") != kind:
        raise HTTPException(401, "Wrong token type")
    return d["sub"]


def current_user(authorization: str | None = Header(None), access_token: str | None = Query(None),
                 db: Session = Depends(get_db)) -> User:
    """Bearer header, or ?access_token= (only needed for EventSource, which cannot set headers)."""
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:]
    elif access_token:
        raw = access_token
    if not raw:
        raise HTTPException(401, "Not authenticated")
    user = db.get(User, decode(raw, "access"))
    if not user:
        raise HTTPException(401, "User not found")
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin only")
    return user


# ---- signed media URLs (so <img>/<video> work without auth headers; short-lived, per asset+variant) ----
def _sig(asset_id: str, variant: str, exp: int) -> str:
    mac = hmac.new(get_settings().jwt_secret.encode(), f"{asset_id}:{variant}:{exp}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac[:18]).decode()


def media_url(asset_id: str, variant: str) -> str:
    exp = int(time.time()) + get_settings().media_url_ttl_s
    return f"/api/v1/media/{asset_id}/{variant}?exp={exp}&sig={_sig(asset_id, variant, exp)}"


def verify_media(asset_id: str, variant: str, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(sig, _sig(asset_id, variant, exp))
