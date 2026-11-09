# app/comments/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload

from app.comments.models import Comment
from app.posts.models import Vote
from app.accounts.services import update_karma
from app.communities.services import is_moderator

# ----------------------------------------------------------------
# コメントの作成
# ----------------------------------------------------------------

async def create_comment(
    db: AsyncSession,
    body: str,
    author_id: uuid.UUID,
    post_id: uuid.UUID,
    parent_id: uuid.UUID | None = None
) -> Comment:
    if not body or len(body.strip()) == 0:
        raise ValueError("コメントの本文は必須です")
    if len(body) > 10_000:
        raise ValueError("コメントは10,000文字以内にしてください")

    if parent_id is not None:
        # 返信先の存在と、同じ投稿への所属を確認する
        # （存在しない parent_id を DB の外部キーエラーで落とさないため）
        parent = await db.get(Comment, parent_id)
        if parent is None:
            raise ValueError("返信先のコメントが見つかりません")
        if parent.post_id != post_id:
            raise ValueError("返信先のコメントがこの投稿に属していません")

    comment = Comment(
        body=body,
        author_id=author_id,
        post_id=post_id,
        parent_id=parent_id
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)

    # author を eager load する
    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment.id)
        .options(selectinload(Comment.author))
    )
    return result.scalar_one()


# ----------------------------------------------------------------
# コメントの取得（ツリー構造）
# ----------------------------------------------------------------

async def list_comments(
    db: AsyncSession, post_id: uuid.UUID
) -> list[Comment]:
    """
    投稿のコメントをツリー構造で返す。
    1回のクエリで全コメントを取得してからメモリ上でツリーを組み立てる。
    """
    result = await db.execute(
        select(Comment)
        .where(Comment.post_id == post_id)
        .options(selectinload(Comment.author))
        .order_by(Comment.inserted_at.asc())
    )
    comments = list(result.scalars().all())
    return _build_tree(comments)


def _build_tree(comments: list[Comment]) -> list[Comment]:
    """フラットなリストをツリー構造に変換する"""
    # parent_id ごとにグループ化する
    by_parent: dict[uuid.UUID | None, list[Comment]] = {}
    for comment in comments:
        key = comment.parent_id
        if key not in by_parent:
            by_parent[key] = []
        by_parent[key].append(comment)

    # 再帰的にツリーを組み立てる
    def build_children(parent_id: uuid.UUID | None) -> list[Comment]:
        children = by_parent.get(parent_id, [])
        for child in children:
            child.children = build_children(child.id)
        return children

    return build_children(None)


# ----------------------------------------------------------------
# コメントへの投票
# ----------------------------------------------------------------

async def vote_comment(
    db: AsyncSession, user_id: uuid.UUID,
    comment_id: uuid.UUID, value: int
) -> Comment:
    """
    コメントに投票する。Posts の vote_post と同じ4パターン。
    """
    if value not in (1, -1):
        raise ValueError("投票値は 1 または -1 のみ有効です")

    result = await db.execute(
        select(Comment)
        .where(Comment.id == comment_id)
        .options(selectinload(Comment.author))
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise ValueError("コメントが見つかりません")

    # 自分のコメントには投票できない
    if comment.author_id == user_id:
        raise ValueError("自分のコメントには投票できません")

    # 既存の投票を確認する
    existing = await db.execute(
        select(Vote).where(
            and_(
                Vote.user_id == user_id,
                Vote.target_type == "comment",
                Vote.target_id == comment_id
            )
        )
    )
    existing_vote = existing.scalar_one_or_none()

    if existing_vote is None:
        # パターンA: 新規投票
        db.add(Vote(
            user_id=user_id,
            target_type="comment",
            target_id=comment_id,
            value=value
        ))
        await _update_comment_score(db, comment, value)
        await update_karma(db, comment.author_id, "comment", value)

    elif existing_vote.value == value:
        # パターンB: 同じ方向 → 取り消し
        await db.delete(existing_vote)
        await _update_comment_score(db, comment, -value)
        await update_karma(db, comment.author_id, "comment", -value)

    else:
        # パターンC: 逆方向 → 変更
        diff = value - existing_vote.value
        existing_vote.value = value
        await _update_comment_score(db, comment, diff)
        await update_karma(db, comment.author_id, "comment", diff)

    await db.flush()
    await db.refresh(comment)
    return comment


async def _update_comment_score(
    db: AsyncSession, comment: Comment, diff: int
) -> None:
    new_score = comment.score + diff
    await db.execute(
        update(Comment)
        .where(Comment.id == comment.id)
        .values(score=new_score)
    )
    comment.score = new_score


# ----------------------------------------------------------------
# コメントの削除
# ----------------------------------------------------------------

async def delete_comment(
    db: AsyncSession,
    comment_id: uuid.UUID,
    user_id: uuid.UUID,
    subreddit_id: uuid.UUID
) -> None:
    """
    コメントを削除する。
    本人またはモデレーターのみ削除できる。
    子コメントは DB の CASCADE で自動的に削除される。
    """
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    comment = result.scalar_one_or_none()
    if comment is None:
        raise ValueError("コメントが見つかりません")

    moderator = await is_moderator(db, user_id, subreddit_id)

    if comment.author_id != user_id and not moderator:
        raise PermissionError("削除する権限がありません")

    await db.delete(comment)
