# app/auth.py
from itsdangerous import URLSafeTimedSerializer, BadSignature
from fastapi import Response, Request
from app.config import settings

COOKIE_MAX_AGE = 60 * 60 * 24 * 7   # 7日間（秒）

def create_session_token(user_id: str) -> str:
    """user_id を署名してトークンを生成する"""
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(user_id, salt="session")


def verify_session_token(token: str) -> str | None:
    """
    トークンを検証して user_id を返す。
    無効または期限切れの場合は None を返す。
    """
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return s.loads(token, salt="session", max_age=COOKIE_MAX_AGE)
    except BadSignature:
        return None


def set_session_cookie(response: Response, user_id: str) -> None:
    """レスポンスに Cookie をセットする"""
    token = create_session_token(str(user_id))
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,     # JavaScript からアクセスできない（XSS 対策）
        samesite="lax",    # CSRF 対策
        secure=not settings.DEBUG  # 本番では HTTPS のみ
    )


def clear_session_cookie(response: Response) -> None:
    """Cookie を削除する（ログアウト）"""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax"
    )
