# app/accounts/schemas.py
import uuid
from pydantic import BaseModel, EmailStr, field_validator
import re

class UserCreate(BaseModel):
    """ユーザー登録フォームのバリデーション"""
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 20:
            raise ValueError("ユーザー名は3〜20文字にしてください")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("ユーザー名は英数字とアンダースコアのみ使用できます")
        return v.lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("パスワードは8文字以上にしてください")
        return v

class UserResponse(BaseModel):
    """ユーザー情報のレスポンス"""
    id: uuid.UUID
    username: str
    post_karma: int
    comment_karma: int

    model_config = {"from_attributes": True}  # SQLAlchemy Model から変換できる
