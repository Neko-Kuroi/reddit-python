# app/communities/router.py
from fastapi import APIRouter, Depends, Query, Request, Form, HTTPException
from typing import Literal
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_auth
from app.communities import services
from app.communities.schemas import SubredditCreate
from app.posts.services import list_posts

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# Subreddit ページ
# ----------------------------------------------------------------

@router.get("/r/{name}", response_class=HTMLResponse)
async def subreddit_page(
    request: Request,
    name: str,
    sort: Literal["hot", "new"] = Query("hot"),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404, detail=f"r/{name} は存在しません")

    posts, has_more = await list_posts(db, subreddit.id, sort, page)
    joined = False
    if current_user:
        joined = await services.is_member(db, current_user.id, subreddit.id)

    return templates.TemplateResponse(
        "communities/subreddit.html",
        {
            "request": request,
            "current_user": current_user,
            "subreddit": subreddit,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": has_more,
            "joined": joined
        }
    )


# ----------------------------------------------------------------
# もっと見る（HTMX）
# ----------------------------------------------------------------

@router.get("/r/{name}/posts", response_class=HTMLResponse)
async def load_more_posts(
    request: Request,
    name: str,
    sort: Literal["hot", "new"] = Query("hot"),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """HTMX からの追加読み込みリクエスト"""
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    posts, has_more = await list_posts(db, subreddit.id, sort, page)

    return templates.TemplateResponse(
        "components/post_list.html",
        {
            "request": request,
            "current_user": current_user,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": has_more,
            "subreddit": subreddit
        }
    )


# ----------------------------------------------------------------
# Join / Leave（HTMX）
# ----------------------------------------------------------------

@router.post("/r/{name}/join", response_class=HTMLResponse)
async def join_subreddit(
    request: Request,
    name: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    try:
        await services.join_subreddit(db, current_user.id, subreddit.id)
    except ValueError:
        pass   # すでに参加済みは無視する

    # Join ボタン → 参加中ボタンに差し替える HTML を返す
    return templates.TemplateResponse(
        "components/join_button.html",
        {
            "request": request,
            "subreddit": subreddit,
            "joined": True
        }
    )


@router.post("/r/{name}/leave", response_class=HTMLResponse)
async def leave_subreddit(
    request: Request,
    name: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    try:
        await services.leave_subreddit(db, current_user.id, subreddit.id)
        joined = False
    except ValueError as e:
        # オーナーは脱退できない
        joined = True

    return templates.TemplateResponse(
        "components/join_button.html",
        {
            "request": request,
            "subreddit": subreddit,
            "joined": joined
        }
    )


# ----------------------------------------------------------------
# Subreddit 作成
# ----------------------------------------------------------------

@router.get("/subreddits/new", response_class=HTMLResponse)
async def new_subreddit_page(
    request: Request,
    current_user=Depends(require_auth)
):
    return templates.TemplateResponse(
        "communities/new_subreddit.html",
        {"request": request, "current_user": current_user, "errors": {}}
    )


@router.post("/subreddits/new")
async def create_subreddit(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    errors = {}

    try:
        data = SubredditCreate(name=name, description=description or None)
    except Exception as e:
        for error in e.errors():
            errors[error["loc"][0]] = error["msg"]
        return templates.TemplateResponse(
            "communities/new_subreddit.html",
            {"request": request, "current_user": current_user,
             "errors": errors, "name": name, "description": description},
            status_code=422
        )

    try:
        subreddit = await services.create_subreddit(db, data, current_user.id)
    except ValueError as e:
        errors["name"] = str(e)
        return templates.TemplateResponse(
            "communities/new_subreddit.html",
            {"request": request, "current_user": current_user,
             "errors": errors, "name": name, "description": description},
            status_code=422
        )

    return RedirectResponse(url=f"/r/{subreddit.name}", status_code=303)
