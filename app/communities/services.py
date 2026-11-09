# app/communities/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, and_
from sqlalchemy.exc import IntegrityError

from app.communities.models import Subreddit, SubredditMember
from app.communities.schemas import SubredditCreate

# ----------------------------------------------------------------
# Subreddit の作成
# ----------------------------------------------------------------

async def create_subreddit(
    db: AsyncSession, data: SubredditCreate, owner_id: uuid.UUID
) -> Subreddit:
    """
    Subreddit を作成する。
    作成者を moderator として自動的に登録する。
    トランザクションで両方の操作を保護する。
    """
    # 大文字小文字を区別しないよう、保存前に小文字へそろえる
    name = data.name.lower()

    # 名前の重複チェック
    existing = await db.execute(
        select(Subreddit).where(Subreddit.name == name)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"r/{name} はすでに存在します")

    # Subreddit を作成
    subreddit = Subreddit(
        name=name,
        description=data.description,
        owner_id=owner_id
    )
    db.add(subreddit)
    try:
        await db.flush()   # subreddit.id を確定させる

        # 作成者を moderator として登録
        member = SubredditMember(
            user_id=owner_id,
            subreddit_id=subreddit.id,
            role="moderator"
        )
        db.add(member)
        await db.flush()
        await db.refresh(subreddit)
    except IntegrityError:
        # 重複チェック後に別のリクエストが先に作成した場合は重複として返す
        await db.rollback()
        raise ValueError(f"r/{name} はすでに存在します")

    return subreddit


# ----------------------------------------------------------------
# Subreddit の取得
# ----------------------------------------------------------------

async def get_subreddit_by_name(
    db: AsyncSession, name: str
) -> Subreddit | None:
    result = await db.execute(
        select(Subreddit).where(Subreddit.name == name.lower())
    )
    return result.scalar_one_or_none()


async def get_subreddit_by_id(
    db: AsyncSession, subreddit_id: uuid.UUID
) -> Subreddit | None:
    result = await db.execute(
        select(Subreddit).where(Subreddit.id == subreddit_id)
    )
    return result.scalar_one_or_none()


# ----------------------------------------------------------------
# Join / Leave
# ----------------------------------------------------------------

async def join_subreddit(
    db: AsyncSession, user_id: uuid.UUID, subreddit_id: uuid.UUID
) -> SubredditMember:
    """Subreddit に参加する"""
    # すでに参加済みかチェック
    if await is_member(db, user_id, subreddit_id):
        raise ValueError("すでに参加しています")

    member = SubredditMember(
        user_id=user_id,
        subreddit_id=subreddit_id,
        role="member"
    )
    db.add(member)
    await db.flush()
    return member


async def leave_subreddit(
    db: AsyncSession, user_id: uuid.UUID, subreddit_id: uuid.UUID
) -> None:
    """Subreddit から脱退する。オーナーは脱退できない。"""
    subreddit = await get_subreddit_by_id(db, subreddit_id)

    if subreddit and subreddit.owner_id == user_id:
        raise ValueError("作成者はコミュニティを脱退できません")

    result = await db.execute(
        select(SubredditMember).where(
            and_(
                SubredditMember.user_id == user_id,
                SubredditMember.subreddit_id == subreddit_id
            )
        )
    )
    member = result.scalar_one_or_none()
    if member:
        await db.delete(member)


# ----------------------------------------------------------------
# 参加確認
# ----------------------------------------------------------------

async def is_member(
    db: AsyncSession, user_id: uuid.UUID, subreddit_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(exists().where(
            and_(
                SubredditMember.user_id == user_id,
                SubredditMember.subreddit_id == subreddit_id
            )
        ))
    )
    return result.scalar()


async def is_moderator(
    db: AsyncSession, user_id: uuid.UUID, subreddit_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(exists().where(
            and_(
                SubredditMember.user_id == user_id,
                SubredditMember.subreddit_id == subreddit_id,
                SubredditMember.role == "moderator"
            )
        ))
    )
    return result.scalar()


# ----------------------------------------------------------------
# 一覧取得
# ----------------------------------------------------------------

async def list_joined_subreddits(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Subreddit]:
    """ユーザーが参加しているSubreddit一覧（サイドバー用）"""
    result = await db.execute(
        select(Subreddit)
        .join(SubredditMember, SubredditMember.subreddit_id == Subreddit.id)
        .where(SubredditMember.user_id == user_id)
        .order_by(Subreddit.name)
    )
    return list(result.scalars().all())


async def search_subreddits(
    db: AsyncSession, query: str
) -> list[Subreddit]:
    """キーワードでSubredditを検索する"""
    if not query:
        return []

    term = f"%{query}%"
    result = await db.execute(
        select(Subreddit)
        .where(
            Subreddit.name.ilike(term) | Subreddit.description.ilike(term)
        )
        .order_by(Subreddit.name)
        .limit(10)
    )
    return list(result.scalars().all())
