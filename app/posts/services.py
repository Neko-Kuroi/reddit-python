# app/posts/services.py
import uuid
import math
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.posts.models import Post, Vote
from app.posts.schemas import PostCreate
from app.accounts.services import update_karma
from app.communities.models import SubredditMember
from app.communities.services import is_moderator

PAGE_SIZE = 25

# ----------------------------------------------------------------
# 投稿の作成
# ----------------------------------------------------------------

async def create_post(
    db: AsyncSession, data: PostCreate,
    author_id: uuid.UUID, subreddit_id: uuid.UUID
) -> Post:
    hot_score = Post.compute_hot_score(0, datetime.now(timezone.utc))

    post = Post(
        title=data.title,
        type=data.type,
        body=data.body,
        url=data.url,
        author_id=author_id,
        subreddit_id=subreddit_id,
        hot_score=hot_score
    )
    db.add(post)
    await db.flush()
    await db.refresh(post)
    return post


# ----------------------------------------------------------------
# 投稿の取得
# ----------------------------------------------------------------

async def get_post(db: AsyncSession, post_id: uuid.UUID) -> Post | None:
    result = await db.execute(
        select(Post)
        .where(Post.id == post_id)
        .options(
            selectinload(Post.author),
            selectinload(Post.subreddit)
        )
    )
    return result.scalar_one_or_none()


# ----------------------------------------------------------------
# Feed の取得
# ----------------------------------------------------------------

async def list_posts(
    db: AsyncSession, subreddit_id: uuid.UUID,
    sort: str = "hot", page: int = 1
) -> tuple[list[Post], bool]:
    """Subreddit の投稿一覧（コメント数付き）と次ページの有無"""
    from app.comments.models import Comment

    offset = (page - 1) * PAGE_SIZE

    query = (
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .where(Post.subreddit_id == subreddit_id)
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .limit(PAGE_SIZE + 1)
        .offset(offset)
    )
    query = _apply_sort(query, sort)

    result = await db.execute(query)
    rows = result.all()

    has_more = len(rows) > PAGE_SIZE
    posts = []
    for post, comment_count in rows[:PAGE_SIZE]:
        post.comment_count = comment_count
        posts.append(post)
    return posts, has_more


async def list_home_posts(
    db: AsyncSession, user_id: uuid.UUID,
    sort: str = "hot", page: int = 1
) -> tuple[list[Post], bool]:
    """ホーム Feed（Join 済みの投稿一覧）と次ページの有無"""
    from app.comments.models import Comment

    offset = (page - 1) * PAGE_SIZE

    query = (
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .join(SubredditMember, SubredditMember.subreddit_id == Post.subreddit_id)
        .where(SubredditMember.user_id == user_id)
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .limit(PAGE_SIZE + 1)
        .offset(offset)
    )
    query = _apply_sort(query, sort)

    result = await db.execute(query)
    rows = result.all()

    has_more = len(rows) > PAGE_SIZE
    posts = []
    for post, comment_count in rows[:PAGE_SIZE]:
        post.comment_count = comment_count
        posts.append(post)
    return posts, has_more


async def list_user_posts(
    db: AsyncSession, user_id: uuid.UUID,
    sort: str = "new", page: int = 1
) -> tuple[list[Post], bool]:
    """ユーザーの投稿一覧（プロフィールページ用）と次ページの有無"""
    from app.comments.models import Comment

    offset = (page - 1) * PAGE_SIZE

    query = (
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .where(Post.author_id == user_id)
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .limit(PAGE_SIZE + 1)
        .offset(offset)
    )
    query = _apply_sort(query, sort)

    result = await db.execute(query)
    rows = result.all()

    has_more = len(rows) > PAGE_SIZE
    posts = []
    for post, comment_count in rows[:PAGE_SIZE]:
        post.comment_count = comment_count
        posts.append(post)
    return posts, has_more


async def search_posts(db: AsyncSession, query: str) -> list[Post]:
    """キーワードで投稿を検索する"""
    if not query:
        return []
    from app.comments.models import Comment

    term = f"%{query}%"
    result = await db.execute(
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .where(Post.title.ilike(term))
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .order_by(Post.hot_score.desc(), Post.id.desc())
        .limit(25)
    )
    rows = result.all()

    posts = []
    for post, comment_count in rows:
        post.comment_count = comment_count
        posts.append(post)
    return posts


def _apply_sort(query, sort: str):
    if sort == "new":
        return query.order_by(Post.inserted_at.desc(), Post.id.desc())
    return query.order_by(Post.hot_score.desc(), Post.id.desc())


# ----------------------------------------------------------------
# 投票
# ----------------------------------------------------------------

async def vote_post(
    db: AsyncSession, user_id: uuid.UUID,
    post_id: uuid.UUID, value: int
) -> Post:
    """
    投稿に投票する。4つのパターンを処理する。

    パターンA: 新規投票
    パターンB: 同じ方向 → 取り消し
    パターンC: 逆方向   → 変更
    パターンD: 自分の投稿 → エラー
    """
    if value not in (1, -1):
        raise ValueError("投票値は 1 または -1 のみ有効です")

    post = await get_post(db, post_id)
    if post is None:
        raise ValueError("投稿が見つかりません")

    # パターンD: 自分の投稿には投票できない
    if post.author_id == user_id:
        raise ValueError("自分の投稿には投票できません")

    # 既存の投票を確認する
    existing_vote = await _get_vote(db, user_id, "post", post_id)

    if existing_vote is None:
        # パターンA: 新規投票
        try:
            await _create_vote(db, user_id, "post", post_id, value)
        except IntegrityError as e:
            if not _is_vote_unique_violation(e):
                raise
            # 同じ投票が並行して届いた場合は、先に保存された票が正本。
            # スコアを二重に加算せず、現在の投稿をそのまま返す。
            await db.rollback()
            current_post = await get_post(db, post_id)
            if current_post is None:
                raise ValueError("投稿が見つかりません")
            return current_post
        await _update_post_score(db, post, value)
        await update_karma(db, post.author_id, "post", value)

    elif existing_vote.value == value:
        # パターンB: 同じ方向 → 取り消し
        await db.delete(existing_vote)
        await _update_post_score(db, post, -value)
        await update_karma(db, post.author_id, "post", -value)

    else:
        # パターンC: 逆方向 → 変更
        diff = value - existing_vote.value   # 例: +1→-1 なら diff = -2
        existing_vote.value = value
        await _update_post_score(db, post, diff)
        await update_karma(db, post.author_id, "post", diff)

    await db.flush()
    await db.refresh(post)
    return post


async def _get_vote(
    db: AsyncSession, user_id: uuid.UUID,
    target_type: str, target_id: uuid.UUID
) -> Vote | None:
    result = await db.execute(
        select(Vote).where(
            and_(
                Vote.user_id == user_id,
                Vote.target_type == target_type,
                Vote.target_id == target_id
            )
        )
    )
    return result.scalar_one_or_none()


async def _create_vote(
    db: AsyncSession, user_id: uuid.UUID,
    target_type: str, target_id: uuid.UUID, value: int
) -> Vote:
    vote = Vote(
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        value=value
    )
    db.add(vote)
    await db.flush()   # 一意制約の競合はここで検出する
    return vote


def _is_vote_unique_violation(error: IntegrityError) -> bool:
    original = getattr(error, "orig", None)
    diagnostic = getattr(original, "diag", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    return constraint == "ix_votes_unique" or "ix_votes_unique" in str(original)


async def _update_post_score(
    db: AsyncSession, post: Post, diff: int
) -> None:
    # score は DB 側で差分加算する。同時投票でも、互いの更新を
    # Python 側の古い値で上書きしないため。
    new_score = Post.score + diff
    epoch = datetime(2005, 12, 8, 7, 46, 43, tzinfo=timezone.utc)
    seconds = func.extract("epoch", Post.inserted_at - epoch)
    new_hot_score = (
        func.sign(new_score)
        * func.log(10, func.greatest(func.abs(new_score), 1))
        + seconds / 45000.0
    )

    result = await db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(score=new_score, hot_score=new_hot_score)
        .returning(Post.score, Post.hot_score)
    )
    updated_score, updated_hot_score = result.one()
    # Python オブジェクトも DB が確定した値にそろえる
    post.score = updated_score
    post.hot_score = updated_hot_score


# ----------------------------------------------------------------
# 投稿の削除
# ----------------------------------------------------------------

async def delete_post(
    db: AsyncSession, post_id: uuid.UUID,
    user_id: uuid.UUID, subreddit_id: uuid.UUID
) -> None:
    """
    投稿を削除する。
    本人またはモデレーターのみ削除できる。
    削除後に Karma は戻さない（Reddit と同じ仕様）。
    """
    post = await get_post(db, post_id)
    if post is None:
        raise ValueError("投稿が見つかりません")

    moderator = await is_moderator(db, user_id, subreddit_id)

    if post.author_id != user_id and not moderator:
        raise PermissionError("削除する権限がありません")

    await db.delete(post)
