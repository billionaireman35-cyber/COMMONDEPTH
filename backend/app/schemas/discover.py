from pydantic import BaseModel, ConfigDict

from app.schemas.content import PostResponse


class DiscoverListResponse(BaseModel):
    items: list[PostResponse]
    next_cursor: str | None = None

    model_config = ConfigDict(extra="forbid")
