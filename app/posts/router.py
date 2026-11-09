# app/posts/router.py
from fastapi import APIRouter, Depends, Query, Request, Form, HTTPException
from typing import Literal
from html import escape
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.dependencies import get_current_user, require_auth
from app.posts import services
from app.posts.schemas import PostCreate
from app.communities.services import get_subreddit_by_name
from app.comments.services import list_comments

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# 投稿作成
# ----------------------------------------------------------------

@router.get("/r/{name}/submit", response_class=HTMLResponse)
async def new_post_page(
    request: Request,
    name: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "posts/new_post.html",
        {
            "request": request,
            "current_user": current_user,
            "subreddit": subreddit,
            "errors": {},
            "post_type": "text"
        }
    )


@router.post("/r/{name}/submit")
async def create_post(
    request: Request,
    name: str,
    title: str = Form(...),
    post_type: str = Form(...),
    body: str = Form(""),
    url: str = Form(""),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    errors = {}
    try:
        data = PostCreate(
            title=title,
            type=post_type,
            body=body if post_type == "text" else None,
            url=url if post_type == "link" else None
        )
    except Exception as e:
        for error in e.errors():
            field = error["loc"][0] if error["loc"] else "general"
            errors[field] = error["msg"]
        return templates.TemplateResponse(
            "posts/new_post.html",
            {
                "request": request,
                "current_user": current_user,
                "subreddit": subreddit,
                "errors": errors,
                "post_type": post_type,
                "title": title,
                "body": body,
                "url": url
            },
            status_code=422
        )

    post = await services.create_post(db, data, current_user.id, subreddit.id)
    return RedirectResponse(url=f"/r/{name}/{post.id}", status_code=303)


# ----------------------------------------------------------------
# 投稿詳細ページ
# ----------------------------------------------------------------

@router.get("/r/{name}/{post_id}", response_class=HTMLResponse)
async def post_detail(
    request: Request,
    name: str,
    post_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    post = await services.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    comments = await list_comments(db, post_id)

    return templates.TemplateResponse(
        "posts/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "post": post,
            "comments": comments
        }
    )


# ----------------------------------------------------------------
# 投稿への投票（HTMX）
# ----------------------------------------------------------------

@router.post("/posts/{post_id}/vote", response_class=HTMLResponse)
async def vote_post(
    request: Request,
    post_id: uuid.UUID,
    value: int = Form(...),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    try:
        post = await services.vote_post(db, current_user.id, post_id, value)
    except ValueError as e:
        # 自分の投稿への投票など
        return HTMLResponse(
            content=f'<span class="text-red-500 text-xs">{escape(str(e))}</span>',
            status_code=400
        )

    # 更新後のスコアと投票ボタンの HTML を返す
    return templates.TemplateResponse(
        "components/vote_buttons.html",
        {
            "request": request,
            "target_type": "post",
            "target_id": str(post_id),
            "score": post.score,
            "current_user": current_user
        }
    )


# ----------------------------------------------------------------
# 投稿の削除
# ----------------------------------------------------------------

@router.post("/posts/{post_id}/delete")
async def delete_post(
    post_id: uuid.UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    post = await services.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404)

    subreddit_name = post.subreddit.name

    try:
        await services.delete_post(db, post_id, current_user.id, post.subreddit_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="削除する権限がありません")

    return RedirectResponse(url=f"/r/{subreddit_name}", status_code=303)


# ----------------------------------------------------------------
# ホーム Feed
# ----------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    sort: Literal["hot", "new"] = Query("hot"),
    page: int = Query(1, ge=1),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    from app.communities.services import list_joined_subreddits

    posts, has_more = await services.list_home_posts(
        db, current_user.id, sort, page
    )
    joined_subreddits = await list_joined_subreddits(db, current_user.id)

    return templates.TemplateResponse(
        "posts/home.html",
        {
            "request": request,
            "current_user": current_user,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": has_more,
            "joined_subreddits": joined_subreddits
        }
    )


# ----------------------------------------------------------------
# 検索
# ----------------------------------------------------------------

@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.communities.services import search_subreddits

    posts = await services.search_posts(db, q) if q else []
    subreddits = await search_subreddits(db, q) if q else []

    return templates.TemplateResponse(
        "posts/search.html",
        {
            "request": request,
            "current_user": current_user,
            "query": q,
            "posts": posts,
            "subreddits": subreddits
        }
    )
