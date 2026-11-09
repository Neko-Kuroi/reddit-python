# app/communities/schemas.py
import uuid
import re
from pydantic import BaseModel, field_validator

class SubredditCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 21:
            raise ValueError("コミュニティ名は3〜21文字にしてください")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("英数字とアンダースコアのみ使用できます")
        return v.lower()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v and len(v) > 500:
            raise ValueError("説明は500文字以内にしてください")
        return v

class SubredditResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}
