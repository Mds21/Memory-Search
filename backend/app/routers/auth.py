import io
import json
import secrets
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import app_settings, google_auth
from ..adapters import registry
from ..db import get_db
from ..models import Asset, AssetTag, Collection, Conversation, Tag, User
from ..schemas import GoogleIn, GoogleSettingIn, GoogleEnabledIn, LoginIn, ProfilePatch, RefreshIn, RegisterIn
from ..security import admin_user, current_user, decode, hash_password, make_tokens, verify_password

router = APIRouter(tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "display_name": u.display_name, "language": u.language, "timezone": u.timezone, "is_admin": u.is_admin}


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(409, "An account with this email already exists")
    first = db.query(User).count() == 0
    u = User(email=email, hashed_password=hash_password(body.password), display_name=body.display_name or email.split("@")[0],
             language=body.language if body.language in {"en", "hi", "mr", "ta", "es"} else "en", is_admin=first)
    db.add(u)
    db.commit()
    return {**make_tokens(u.id), "user": user_out(u)}


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(func.lower(User.email) == body.email.strip().lower()).first()
    if not u or not verify_password(body.password, u.hashed_password):
        raise HTTPException(401, "Incorrect email or password")
    return {**make_tokens(u.id), "user": user_out(u)}


@router.get("/auth/providers")
def providers():
    """What the sign-in page can offer. The Google client id is public by design (it ships in every Google button)."""
    cid = (app_settings.google_client_id() or None) if app_settings.google_enabled() else None  # paused: no button
    return {"password": True, "google_client_id": cid, "google_ready": bool(cid), "password_reset": False}


@router.post("/auth/google")
def google_sign_in(body: GoogleIn, db: Session = Depends(get_db)):
    """Signs in with a Google ID token. Links to an existing account with the same verified email, or creates one."""
    client_id = app_settings.google_client_id()
    if not client_id:
        raise HTTPException(400, "Google sign-in is not set up on this server")
    if not app_settings.google_enabled():
        raise HTTPException(403, "Google sign-in is paused on this server. Sign in with your email and password.")
    claims = google_auth.verify(body.credential, client_id)
    sub, email = claims["sub"], claims["email"].strip().lower()
    u = db.query(User).filter(User.google_sub == sub).first() or db.query(User).filter(func.lower(User.email) == email).first()
    if u is None:
        first = db.query(User).count() == 0
        u = User(email=email, hashed_password=hash_password(secrets.token_urlsafe(32)),  # unusable until they set one
                 display_name=(claims.get("name") or email.split("@")[0])[:120],
                 language=body.language if body.language in {"en", "hi", "mr", "ta", "es"} else "en", is_admin=first)
        db.add(u)
    if not u.google_sub:
        u.google_sub = sub
    db.commit()
    return {**make_tokens(u.id), "user": user_out(u)}


@router.get("/admin/settings/google")
def get_google_setting(_: User = Depends(admin_user)):
    return _google_state()


def _google_state() -> dict:
    return {"client_id": app_settings.google_client_id() or None, "source": app_settings.google_source(),
            "enabled": app_settings.google_enabled()}


@router.put("/admin/settings/google/enabled")
def set_google_enabled(body: GoogleEnabledIn, _: User = Depends(admin_user)):
    """Pause or resume Google sign-in (on by default). Accounts and the Client ID are kept either way."""
    app_settings.save(google_enabled=bool(body.enabled))
    return _google_state()


@router.put("/admin/settings/google")
def put_google_setting(body: GoogleSettingIn, _: User = Depends(admin_user)):
    if app_settings.google_source() == "env":
        raise HTTPException(409, "GOOGLE_CLIENT_ID is set in the server environment. Change it there.")
    cid = body.client_id.strip()
    if cid and not app_settings.GOOGLE_ID_RE.match(cid):
        raise HTTPException(422, "That does not look like a Google Client ID. It ends in .apps.googleusercontent.com")
    app_settings.save(google_client_id=cid or None)
    return _google_state()


@router.post("/auth/refresh")
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    uid = decode(body.refresh_token, "refresh")
    u = db.get(User, uid)
    if not u:
        raise HTTPException(401, "User not found")
    return {**make_tokens(u.id), "user": user_out(u)}  # rotates both tokens


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
