# 全コード付録 3　ルーターと入口（Web 層）

> **このファイルは自動生成です。** 生成スクリプト `~/workspace/reddit_clone_audit/generate_code_appendix_py.py` が、
> 正本のコードファイル（`~/workspace/reddit_clone_python/` 内）から全文を機械的に転記して作りました。
> **正本はコードファイルそのもの**であり、この付録は「すべてのコードがチュートリアル側に収録されている」
> ことを保証するための再録です。コードを直すときは正本を直し、この付録は再生成してください。
>
> 対応する章: 第5章（認証 Router）、第6章（画面の Router）、第7章（報告理由の追加）

---

## app/accounts/router.py

対応: 第5章。正本: `app/accounts/router.py`

```python
# app/accounts/router.py
from fastapi import APIRouter, Depends, Query, Request, Response, Form
from typing import Literal
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
    sort: Literal["hot", "new"] = Query("new"),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.posts.services import list_user_posts

    profile_user = await services.get_user_by_username(db, username)
    if profile_user is None:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )

    posts, has_more = await list_user_posts(
        db, profile_user.id, sort, page
    )

    return templates.TemplateResponse(
        "accounts/profile.html",
        {
            "request": request,
            "current_user": current_user,
            "profile_user": profile_user,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": has_more
        }
    )
```

## app/communities/router.py

対応: 第6章。正本: `app/communities/router.py`

```python
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
```

## app/posts/router.py

対応: 第6章。正本: `app/posts/router.py`

```python
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
```

## app/comments/router.py

対応: 第6章（報告理由の再表示は第7章で追加）。正本: `app/comments/router.py`

```python
# app/comments/router.py
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from html import escape
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.dependencies import get_current_user, require_auth
from app.comments import services
from app.posts.services import get_post

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# コメント投稿
# ----------------------------------------------------------------

@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: uuid.UUID,
    body: str = Form(...),
    parent_id: str = Form(""),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    post = await get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404)

    if parent_id:
        try:
            parent_uuid = uuid.UUID(parent_id)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="parent_id の形式が正しくありません"
            )
    else:
        parent_uuid = None

    try:
        await services.create_comment(
            db,
            body=body,
            author_id=current_user.id,
            post_id=post_id,
            parent_id=parent_uuid
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return RedirectResponse(
        url=f"/r/{post.subreddit.name}/{post_id}",
        status_code=303
    )


# ----------------------------------------------------------------
# コメントへの投票（HTMX）
# ----------------------------------------------------------------

@router.post("/comments/{comment_id}/vote", response_class=HTMLResponse)
async def vote_comment(
    request: Request,
    comment_id: uuid.UUID,
    value: int = Form(...),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    try:
        comment = await services.vote_comment(db, current_user.id, comment_id, value)
    except ValueError as e:
        return HTMLResponse(
            content=f'<span class="text-red-500 text-xs">{escape(str(e))}</span>',
            status_code=400
        )

    return templates.TemplateResponse(
        "components/vote_buttons.html",
        {
            "request": request,
            "target_type": "comment",
            "target_id": str(comment_id),
            "score": comment.score,
            "current_user": current_user
        }
    )


# ----------------------------------------------------------------
# コメントの削除
# ----------------------------------------------------------------

@router.post("/comments/{comment_id}/delete")
async def delete_comment(
    request: Request,
    comment_id: uuid.UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    # subreddit_id は Referer ヘッダーから投稿ページへリダイレクト
    referer = request.headers.get("referer", "/")

    # コメントを取得して subreddit_id を確認する
    from sqlalchemy import select
    from app.comments.models import Comment
    from app.posts.models import Post

    result = await db.execute(
        select(Comment, Post.subreddit_id)
        .join(Post, Post.id == Comment.post_id)
        .where(Comment.id == comment_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404)

    comment, subreddit_id = row

    try:
        await services.delete_comment(db, comment_id, current_user.id, subreddit_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="削除する権限がありません")

    return RedirectResponse(url=referer, status_code=303)


# ----------------------------------------------------------------
# 報告（HTMX）
# ----------------------------------------------------------------

@router.post("/reports", response_class=HTMLResponse)
async def create_report(
    request: Request,
    target_type: str = Form(...),
    target_id: str = Form(...),
    reason: str = Form(...),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    from app.reports.services import create_report as _create_report

    try:
        await _create_report(
            db,
            reporter_id=current_user.id,
            target_type=target_type,
            target_id=uuid.UUID(target_id),
            reason=reason
        )
    except ValueError as e:
        return HTMLResponse(
            content=f'<p class="text-red-500 text-sm">{escape(str(e))}</p>',
            status_code=400
        )

    # 報告成功 → モーダルを閉じる HTML を返す
    return HTMLResponse(
        content='<p class="text-green-600 text-sm text-center py-2">報告しました。ご協力ありがとうございます。</p>'
    )


# === appended from chapter_07.md block 4 ===
# app/comments/router.py に追加

@router.get("/components/report-reasons", response_class=HTMLResponse)
async def report_reasons(request: Request):
    """報告モーダルの理由ボタンをリセットする"""
    return templates.TemplateResponse(
        "components/report_reasons.html",
        {"request": request}
    )
```
