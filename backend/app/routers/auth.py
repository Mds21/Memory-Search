import io
import json
import secrets
import time
import zipfile
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import accounts, app_settings
from ..adapters import registry
from ..config import get_settings
from ..db import get_db
from ..models import Asset, AssetTag, Collection, Conversation, Tag, User
from ..schemas import ContactPatch, ForgotIn, GoogleIn, LoginIn, PasswordChangeIn, ProfilePatch, RefreshIn, RegisterIn, ResetIn
from ..security import admin_user, current_user, decode_claims, hash_password, make_tokens, token_still_valid, verify_password

router = APIRouter(tags=["auth"])
LANGS = {"en", "hi", "mr", "ta", "es"}


def user_out(u: User) -> dict:
    return {"id": u.id, "email": accounts.real_email(u), "phone": u.phone, "username": u.username, "display_name": u.display_name,
            "language": u.language, "timezone": u.timezone, "is_admin": u.is_admin, "google": bool(u.google_sub),
            "has_password": u.password_set is not False, "must_change_password": bool(u.must_change_password)}


def _signed_in(u: User) -> dict:
    return {**make_tokens(u.id, u.token_version or 0), "user": user_out(u)}


def _set_password(u: User, pw: str) -> None:
    accounts.check_password_strength(pw)
    u.hashed_password = hash_password(pw)
    u.password_set = True
    u.must_change_password = False
    u.pw_changed_at = datetime.now(timezone.utc)
    u.token_version = (u.token_version or 0) + 1  # signs out every session started before now


def _clean_email(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    e = raw.strip().lower()
    if not accounts.EMAIL_RE.match(e) or e.endswith(".invalid"):
        raise HTTPException(422, "Please enter a valid email address.")
    return e


def _clean_phone(raw: str | None) -> str | None:
    if not raw or not raw.strip():
        return None
    p = accounts.normalize_phone(raw)
    if not p:
        raise HTTPException(422, "Please enter a valid mobile number, e.g. 98765 43210 or +44 7700 900123.")
    return p


def _taken(db: Session, *, email: str | None = None, phone: str | None = None, username: str | None = None, but: str | None = None) -> None:
    q = db.query(User)
    if but:
        q = q.filter(User.id != but)
    if email and q.filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "An account with this email already exists. Try signing in or “Forgot password”.")
    if phone and q.filter(User.phone == phone).first():
        raise HTTPException(409, "An account with this mobile number already exists. Try signing in or “Forgot password”.")
    if username and q.filter(func.lower(User.username) == username.lower()).first():
        raise HTTPException(409, "That username is taken. Try another.")


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    """Create an account with an email, a mobile number, or both (both then sign in to the same account)."""
    if accounts.limited(f"register:{request.client.host if request.client else '?'}", get_settings().signups_per_hour, 3600):
        raise HTTPException(429, "Too many new accounts from here. Please try again later.")
    email, phone = _clean_email(body.email), _clean_phone(body.phone)
    if not email and not phone:
        raise HTTPException(422, "Enter an email address or a mobile number.")
    accounts.check_password_strength(body.password)
    _taken(db, email=email, phone=phone)
    name = (body.display_name or "").strip() or (email.split("@")[0] if email else "Me")
    u = User(email=email or accounts.placeholder_email(phone), phone=phone, hashed_password=hash_password(body.password),
             display_name=name[:120], language=body.language if body.language in LANGS else "en", is_admin=False)
    db.add(u)
    db.commit()
    return _signed_in(u)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Sign in with an email, a mobile number or a username, plus the password."""
    ident = (body.identifier or body.email or "").strip()
    if not ident:
        raise HTTPException(422, "Enter your email, mobile number or username.")
    key = f"login:{ident.lower()}"
    ip_key = f"login-ip:{request.client.host if request.client else '?'}"
    if accounts.limited(ip_key, 30, 600) or accounts.limited(key + ":peek", 12, 600):
        raise HTTPException(429, "Too many attempts. Please wait a few minutes and try again.")
    u = accounts.find_user(db, ident)
    if u and u.password_set is False:
        raise HTTPException(401, "This account signs in with Google. Use “Continue with Google”, or set a password with “Forgot password”.")
    if not u or not verify_password(body.password, u.hashed_password):
        raise HTTPException(401, "That email, number or username and password don't match. Try again or use “Forgot password”.")
    accounts.clear_limit(key + ":peek")
    return _signed_in(u)


@router.post("/auth/forgot")
def forgot(body: ForgotIn, request: Request, db: Session = Depends(get_db)):
    """Send a 6-digit reset code. The reply never reveals whether the account exists. Off until OTP delivery is added."""
    if not get_settings().password_reset_enabled:
        raise HTTPException(404, "Password reset isn't available yet. Ask the owner of this Smriti for a temporary password.")
    ident = body.identifier.strip()
    if accounts.limited(f"forgot:{ident.lower()}", 3, 900) or accounts.limited(f"forgot-ip:{request.client.host if request.client else '?'}", 10, 900):
        raise HTTPException(429, "Too many requests. Please wait a few minutes before asking for another code.")
    u = accounts.find_user(db, ident)
    channel, dest = accounts.issue_reset(db, u, accounts.kind_of(ident)) if u else ("none", None)
    return {"ok": True, "channel": channel if u else None, "destination": dest,
            "message": "If an account matches, we've sent a 6-digit code. It expires in 15 minutes."}


@router.post("/auth/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    """Set a new password with the emailed code, then sign straight in."""
    if not get_settings().password_reset_enabled:
        raise HTTPException(404, "Password reset isn't available yet.")
    if accounts.limited(f"reset:{body.identifier.strip().lower()}", 10, 900):
        raise HTTPException(429, "Too many attempts. Please ask for a new code in a few minutes.")
    u = accounts.find_user(db, body.identifier)
    if not u or not accounts.consume_reset(db, u, body.code):
        raise HTTPException(400, "That code is wrong or has expired. Ask for a new one.")
    _set_password(u, body.password)
    db.commit()
    return _signed_in(u)


@router.get("/auth/providers")
def providers():
    """Which sign-in options the sign-in page should offer (the Google client id is public by design)."""
    cid = app_settings.google_client_id()
    return {"password": True, "google": True, "google_ready": bool(cid), "google_client_id": cid or None,
            "password_reset": get_settings().password_reset_enabled}


@router.get("/admin/settings/google")
def get_google_setup(user: User = Depends(admin_user)):
    return {"client_id": app_settings.google_client_id() or None, "source": app_settings.google_source()}


@router.put("/admin/settings/google")
def set_google_setup(body: dict, user: User = Depends(admin_user)):
    """The owner pastes the OAuth client id once; sign-in with Google works for everyone immediately."""
    if app_settings.google_source() == "env":
        raise HTTPException(409, "Google sign-in is set in the server configuration file, so it can't be changed here.")
    cid = str(body.get("client_id") or "").strip()
    if cid and not app_settings.GOOGLE_ID_RE.match(cid):
        raise HTTPException(422, "That doesn't look like a Google Client ID. It ends with “.apps.googleusercontent.com”.")
    app_settings.save(google_client_id=cid or None)
    return {"client_id": cid or None, "source": app_settings.google_source()}


GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def verify_google_credential(credential: str) -> dict:
    """Check a Google ID token with Google and return its claims.

    Google's tokeninfo endpoint validates the signature and expiry; we additionally require that the token was
    issued for *this* app (aud), by Google (iss), for a verified email. Anything else is rejected.
    """
    cid = app_settings.google_client_id()
    if not cid:
        raise HTTPException(404, "Google sign-in isn't switched on yet. The owner of this Smriti can turn it on in Settings.")
    try:
        r = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential}, timeout=10)
    except httpx.HTTPError:
        raise HTTPException(503, "Couldn't reach Google. Check your internet connection and try again.")
    if r.status_code != 200:
        raise HTTPException(401, "Google sign-in failed. Please try again.")
    claims = r.json()
    if claims.get("aud") != cid or claims.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(401, "This Google sign-in wasn't meant for this app.")
    if str(claims.get("email_verified")).lower() != "true" or not claims.get("email"):
        raise HTTPException(401, "Your Google account's email isn't verified.")
    if int(claims.get("exp", 0)) < time.time():
        raise HTTPException(401, "Google sign-in expired. Please try again.")
    return claims


@router.post("/auth/google")
def google_login(body: GoogleIn, db: Session = Depends(get_db)):
    """Sign in (or sign up) with a Google ID token from the "Sign in with Google" button."""
    c = verify_google_credential(body.credential)
    sub, email = str(c["sub"]), c["email"].strip().lower()
    u = db.query(User).filter(User.google_sub == sub).first()
    if not u:
        # same verified email as an existing account: link it, so both ways of signing in reach the same library
        u = db.query(User).filter(func.lower(User.email) == email).first()
        if u:
            u.google_sub = sub
        else:
            lang = (c.get("locale") or "en")[:2]
            u = User(email=email, hashed_password=hash_password(secrets.token_urlsafe(32)), password_set=False, google_sub=sub,
                     display_name=(c.get("name") or email.split("@")[0])[:120],
                     language=lang if lang in LANGS else (body.language if body.language in LANGS else "en"), is_admin=False)
            db.add(u)
    db.commit()
    return _signed_in(u)


@router.post("/auth/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    claims = decode_claims(body.refresh_token, "refresh")
    u = db.get(User, claims["sub"])
    if not u or not token_still_valid(u, claims):
        raise HTTPException(401, "Your session has ended. Please sign in again.")
    return _signed_in(u)  # rotates both tokens


@router.post("/me/password")
def change_password(body: PasswordChangeIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Change your password (Google-only accounts can set one without a current password). Other sessions sign out."""
    if u.password_set is not False and not u.must_change_password:
        if not body.current_password or not verify_password(body.current_password, u.hashed_password):
            raise HTTPException(400, "Your current password isn't right.")
    elif u.must_change_password and body.current_password and not verify_password(body.current_password, u.hashed_password):
        raise HTTPException(400, "Your current password isn't right.")
    if body.current_password and body.current_password == body.new_password:
        raise HTTPException(422, "Choose a password different from the current one.")
    was_first = bool(u.must_change_password)
    _set_password(u, body.new_password)
    db.commit()
    if was_first and u.username == get_settings().admin_username:
        (get_settings().data_path / "admin-credentials.txt").unlink(missing_ok=True)  # the one-time password is no longer valid
    return _signed_in(u)  # fresh tokens for this device


@router.patch("/me/contact")
def update_contact(body: ContactPatch, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Add or change email / mobile / username on one account, so any of them signs in."""
    if u.password_set is not False and not (body.current_password and verify_password(body.current_password, u.hashed_password)):
        raise HTTPException(400, "Enter your current password to change how you sign in.")
    email = _clean_email(body.email) if body.email is not None else None
    phone = _clean_phone(body.phone) if body.phone is not None else None
    username = None
    if body.username is not None and body.username.strip():
        username = body.username.strip().lower()
        if not accounts.USERNAME_RE.match(username):
            raise HTTPException(422, "Usernames are 3–30 letters, numbers, dots or underscores, starting with a letter.")
    _taken(db, email=email, phone=phone, username=username, but=u.id)
    # empty means "remove" only when there is something to remove; an account must keep a way to reach it
    if body.email is not None:
        if email:
            u.email = email
        elif accounts.real_email(u):
            if u.google_sub:
                raise HTTPException(422, "This email is linked to your Google sign-in, so it can't be removed.")
            if not (phone or u.phone) and not u.username:
                raise HTTPException(422, "Keep an email or a mobile number on your account.")
            u.email = accounts.placeholder_email(phone or u.phone) if (phone or u.phone) else f"{u.username}@admin.invalid"
    if body.phone is not None:
        if phone:
            u.phone = phone
            if not accounts.real_email(u) and u.email.endswith("@phone.invalid"):
                u.email = accounts.placeholder_email(phone)
        elif u.phone:
            if not accounts.real_email(u) and not u.username:
                raise HTTPException(422, "Keep an email or a mobile number on your account.")
            u.phone = None
    if body.username is not None:
        u.username = username
    db.commit()
    return user_out(u)


# ---------------- owner tools: users ----------------

@router.get("/admin/users")
def list_users(admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(User).order_by(User.created_at).all()
    return {"items": [{**user_out(x), "created_at": x.created_at} for x in rows]}


@router.post("/admin/users/{uid}/reset-password")
def admin_reset_password(uid: str, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Give someone a temporary password (shown once); they must choose their own at next sign-in."""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    temp = secrets.token_urlsafe(8)
    u.hashed_password = hash_password(temp)
    u.password_set = True
    u.must_change_password = True
    u.pw_changed_at = datetime.now(timezone.utc)
    u.token_version = (u.token_version or 0) + 1
    db.commit()
    return {"temporary_password": temp, "user": user_out(u)}


@router.patch("/admin/users/{uid}")
def admin_update_user(uid: str, body: dict, admin: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if "is_admin" in body:
        make = bool(body["is_admin"])
        if not make and db.query(User).filter(User.is_admin.is_(True), User.id != u.id).count() == 0:
            raise HTTPException(409, "There must always be at least one administrator.")
        u.is_admin = make
    db.commit()
    return user_out(u)


@router.post("/auth/logout")
def logout():
    return {"ok": True}  # stateless tokens: the client discards them


@router.get("/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@router.patch("/me")
def patch_me(body: ProfilePatch, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.display_name is not None:
        u.display_name = body.display_name[:120]
    if body.language in {"en", "hi", "mr", "ta", "es"}:
        u.language = body.language
    if body.timezone:
        u.timezone = body.timezone[:64]
    db.commit()
    return user_out(u)


@router.get("/me/export")
def export(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """ZIP with a metadata JSON of everything the user owns (files themselves are not included)."""
    assets = db.query(Asset).filter_by(owner_id=u.id).all()
    tag_rows = db.execute(select(AssetTag.asset_id, Tag.name).join(Tag, Tag.id == AssetTag.tag_id).where(Tag.owner_id == u.id)).all()
    tags: dict[str, list[str]] = {}
    for aid, n in tag_rows:
        tags.setdefault(aid, []).append(n)
    data = {
        "exported_at": datetime.now(timezone.utc).isoformat(), "user": user_out(u),
        "assets": [{"id": a.id, "kind": a.kind, "filename": a.filename, "taken_at": a.taken_at.isoformat() if a.taken_at else None,
                    "place": a.place_name, "caption": a.caption_user, "tags": tags.get(a.id, []), "size_bytes": a.size_bytes} for a in assets],
        "collections": [{"id": c.id, "name": c.name} for c in db.query(Collection).filter_by(owner_id=u.id)],
        "conversations": db.query(Conversation).filter_by(owner_id=u.id).count(),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("smriti-export.json", json.dumps(data, indent=2, ensure_ascii=False))
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="smriti-export.zip"'})


@router.delete("/me", status_code=204)
def delete_me(u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Deletes the account and ALL derived data (files, thumbnails, chunks, tags, conversations...)."""
    for a in db.query(Asset).filter_by(owner_id=u.id).all():
        db.delete(a)
    registry.store().delete_prefix(u.id)
    for model in (Collection, Conversation, Tag):
        for row in db.query(model).filter_by(owner_id=u.id).all():
            db.delete(row)
    from ..models import Feedback, SavedSearch
    db.query(Feedback).filter_by(owner_id=u.id).delete()
    db.query(SavedSearch).filter_by(owner_id=u.id).delete()
    db.delete(u)
    db.commit()
    return Response(status_code=204)
