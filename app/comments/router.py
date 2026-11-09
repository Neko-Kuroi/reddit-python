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
