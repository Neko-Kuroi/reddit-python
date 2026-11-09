# app/posts/schemas.py
import uuid
from typing import Literal
from pydantic import BaseModel, field_validator, model_validator

class PostCreate(BaseModel):
    title: str
    type: Literal["text", "link"]
    body: str | None = None
    url: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 300:
            raise ValueError("タイトルは1〜300文字にしてください")
        return v

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str | None) -> str | None:
        # 原典 Elixir 版の仕様に合わせ、本文は最大 40,000 文字
        if v is not None and len(v) > 40_000:
            raise ValueError("本文は40,000文字以内にしてください")
        return v

    @model_validator(mode="after")
    def validate_by_type(self) -> "PostCreate":
        """type に応じて body または url を必須にする"""
        if self.type == "text" and not self.body:
            raise ValueError("テキスト投稿には本文が必要です")
        if self.type == "link":
            if not self.url:
                raise ValueError("リンク投稿には URL が必要です")
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("URL は http:// または https:// で始まる必要があります")
        return self

class PostResponse(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    body: str | None
    url: str | None
    score: int
    comment_count: int = 0

    model_config = {"from_attributes": True}
