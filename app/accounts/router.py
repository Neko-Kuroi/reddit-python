# app/accounts/router.py
from fastapi import APIRouter, Depends, Request, Response, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, redirect_if_authenticated
from app.accounts import services
from app.accounts.schemas import UserCreate
from app.auth import set_session_cookie, clear_session_cookie

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# 登録
# ----------------------------------------------------------------

@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    _=Depends(redirect_if_authenticated)
):
    """登録ページを表示する"""
    return templates.TemplateResponse(
        "accounts/register.html",
        {"request": request, "errors": {}}
    )


@router.post("/register")
async def register(
    request: Request,
    response: Response,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """ユーザーを登録する"""
    errors = {}

    # Pydantic でバリデーション
    try:
        data = UserCreate(username=username, email=email, password=password)
    except Exception as e:
        for error in e.errors():
            field = error["loc"][0]
            errors[field] = error["msg"]
        return templates.TemplateResponse(
            "accounts/register.html",
            {"request": request, "errors": errors,
             "username": username, "email": email},
            status_code=422
        )

    # DB に保存
    try:
        user = await services.create_user(db, data)
    except ValueError as e:
        errors["general"] = str(e)
        return templates.TemplateResponse(
            "accounts/register.html",
            {"request": request, "errors": errors,
             "username": username, "email": email},
            status_code=422
        )

    # 登録成功 → 自動ログイン
    redirect = RedirectResponse(url="/", status_code=303)
    set_session_cookie(redirect, str(user.id))
    return redirect


# ----------------------------------------------------------------
# ログイン
# ----------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    _=Depends(redirect_if_authenticated)
):
    """ログインページを表示する"""
    return templates.TemplateResponse(
        "accounts/login.html",
        {"request": request, "error": None}
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """ログインする"""
    user = await services.authenticate_user(db, email, password)

    if user is None:
        # 失敗理由は曖昧にする（セキュリティ上の理由）
        return templates.TemplateResponse(
            "accounts/login.html",
            {
                "request": request,
                "error": "メールアドレスまたはパスワードが違います",
                "email": email   # メールは残す・パスワードは残さない
            },
            status_code=401
        )

    # ログイン成功 → Cookie をセット
    redirect = RedirectResponse(url="/", status_code=303)
    set_session_cookie(redirect, str(user.id))
    return redirect


# ----------------------------------------------------------------
# ログアウト
# ----------------------------------------------------------------

@router.post("/logout")
async def logout():
    """ログアウトする（Cookie を削除する）"""
    redirect = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(redirect)
    return redirect


# ----------------------------------------------------------------
# プロフィール
# ----------------------------------------------------------------

@router.get("/u/{username}", response_class=HTMLResponse)
async def profile(
    request: Request,
    username: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.posts.services import list_user_posts

    profile_user = await services.get_user_by_username(db, username)
    if profile_user is None:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )

    posts = await list_user_posts(db, profile_user.id)

    return templates.TemplateResponse(
        "accounts/profile.html",
        {
            "request": request,
            "current_user": current_user,
            "profile_user": profile_user,
            "posts": posts
        }
    )
