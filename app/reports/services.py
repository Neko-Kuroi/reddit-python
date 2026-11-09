# app/reports/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.reports.models import Report
from app.posts.models import Post
from app.comments.models import Comment

VALID_REASONS = ["spam", "harassment", "hate_speech", "misinformation", "other"]

async def create_report(
    db: AsyncSession,
    reporter_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    reason: str
) -> Report:
    """
    投稿またはコメントを報告する。
    自分のコンテンツは報告できない。
    対象が存在しない場合は ValueError を送出する。
    """
    if reason not in VALID_REASONS:
        raise ValueError(f"無効な報告理由です: {reason}")

    if target_type not in ("post", "comment"):
        raise ValueError("target_type は 'post' または 'comment' のみ有効です")

    # 対象の作成者を確認する
    author_id = await _get_author_id(db, target_type, target_id)
    if author_id is None:
        raise ValueError("報告対象が見つかりません")

    if author_id == reporter_id:
        raise ValueError("自分のコンテンツは報告できません")

    report = Report(
        reporter_id=reporter_id,
        target_type=target_type,
        target_id=target_id,
        reason=reason
    )
    db.add(report)
    await db.flush()
    return report


async def _get_author_id(
    db: AsyncSession, target_type: str, target_id: uuid.UUID
) -> uuid.UUID | None:
    if target_type == "post":
        result = await db.execute(
            select(Post.author_id).where(Post.id == target_id)
        )
    else:
        result = await db.execute(
            select(Comment.author_id).where(Comment.id == target_id)
        )
    return result.scalar_one_or_none()
