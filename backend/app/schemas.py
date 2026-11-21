from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = None
    language: str = "en"


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class ProfilePatch(BaseModel):
    display_name: str | None = None
    language: str | None = None
    timezone: str | None = None


class AssetPatch(BaseModel):
    caption_user: str | None = None
    tags: list[str] | None = None
    place_name: str | None = None
    taken_at: str | None = None


class SearchIn(BaseModel):
    query: str | None = None
    parsed: dict | None = None  # edited filter chips: skips query parsing entirely (no LLM call)
    limit: int = Field(40, ge=1, le=100)
    offset: int = Field(0, ge=0)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = None
    input_mode: str = "text"
    ui_language: str = "en"
    parsed_override: dict | None = None


class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None


class CollectionItemsIn(BaseModel):
    asset_ids: list[str]


class SavedSearchIn(BaseModel):
    name: str | None = None
    query: dict
    pinned: bool = False


class FeedbackIn(BaseModel):
    value: int = Field(ge=-1, le=1)
    message_id: str | None = None
    asset_id: str | None = None
    comment: str | None = None


class ReindexIn(BaseModel):
    asset_ids: list[str] | None = None
    only_failed: bool = False
