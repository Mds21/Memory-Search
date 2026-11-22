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


def _token(sub: str, kind: str, ttl: timedelta, ver: int = 0) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": sub, "typ": kind, "ver": ver, "iat": now, "exp": now + ttl}, get_settings().jwt_secret, algorithm=_ALG)


def make_tokens(user_id: str, ver: int = 0) -> dict:
    s = get_settings()
    return {
        "access_token": _token(user_id, "access", timedelta(minutes=s.access_ttl_min), ver),
        "refresh_token": _token(user_id, "refresh", timedelta(days=s.refresh_ttl_days), ver),
        "token_type": "bearer",
        "expires_in": s.access_ttl_min * 60,
    }


def decode_claims(token: str, kind: str) -> dict:
    try:
        d = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALG])
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    if d.get("typ") != kind:
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    return d


def decode(token: str, kind: str) -> str:
    return decode_claims(token, kind)["sub"]


def token_still_valid(user: User, claims: dict) -> bool:
    """Sessions started before the last password change are signed out everywhere (each change bumps the version)."""
    return int(claims.get("ver", 0)) == int(user.token_version or 0)


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
    claims = decode_claims(raw, "access")
    user = db.get(User, claims["sub"])
    if not user or not token_still_valid(user, claims):
        raise HTTPException(401, "Your session has ended. Please sign in again.")
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
    # Round expiry up to a fixed window so the same asset keeps the same URL for a while:
    # browsers can then reuse cached thumbnails across page loads instead of re-downloading.
    ttl = get_settings().media_url_ttl_s
    window = max(60, ttl // 2)
    exp = -(-(int(time.time()) + ttl) // window) * window
    return f"/api/v1/media/{asset_id}/{variant}?exp={exp}&sig={_sig(asset_id, variant, exp)}"


def verify_media(asset_id: str, variant: str, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(sig, _sig(asset_id, variant, exp))
