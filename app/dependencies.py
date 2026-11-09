# app/dependencies.py
import uuid

from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import verify_session_token
from app.config import settings

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cookie からトークンを取り出し、現在のユーザーを返す。
    未ログインの場合は None を返す。
    Elixir版の fetch_current_user Plug に相当する。
    """
    from app.accounts.services import get_user_by_id

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None

    user_id = verify_session_token(token)
    if not user_id:
        return None

    # トークンの中身は文字列なので、DB 照合の前に UUID 型へ変換する
    # （DB 側の UUID 型はドライバによっては文字列を受け付けないため）
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError):
        return None

    return await get_user_by_id(db, user_uuid)


async def require_auth(
    current_user=Depends(get_current_user)
):
    """
    ログインが必要なエンドポイントを保護する。
    未ログインの場合はログインページへリダイレクトする。
    Elixir版の on_mount :require_auth に相当する。
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return current_user


async def redirect_if_authenticated(
    current_user=Depends(get_current_user)
):
    """
    すでにログイン済みのユーザーをホームへリダイレクトする。
    登録・ログインページで使う。
    """
    if current_user is not None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/"}
        )
    return None
