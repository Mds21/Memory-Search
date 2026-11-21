from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Asset, Collection, User


def owned_asset(db: Session, user: User, asset_id: str) -> Asset:
    a = db.get(Asset, asset_id)
    if not a or a.owner_id != user.id:  # 404 (not 403) so ids of other users' assets are not revealed
        raise HTTPException(404, "Asset not found")
    return a


def owned_collection(db: Session, user: User, cid: str) -> Collection:
    c = db.get(Collection, cid)
    if not c or c.owner_id != user.id:
        raise HTTPException(404, "Collection not found")
    return c
