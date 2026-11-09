# 第4章　ビジネスロジック（Service 層）中編

---

## 4-5　Posts Service

```python
# app/posts/services.py
import uuid
import math
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_, or_
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
) -> list[Post]:
    """Subreddit の投稿一覧（コメント数付き）"""
    from app.comments.models import Comment

    offset = (page - 1) * PAGE_SIZE

    query = (
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .where(Post.subreddit_id == subreddit_id)
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .limit(PAGE_SIZE)
        .offset(offset)
    )
    query = _apply_sort(query, sort)

    result = await db.execute(query)
    rows = result.all()

    posts = []
    for post, comment_count in rows:
        post.comment_count = comment_count
        posts.append(post)
    return posts


async def list_home_posts(
    db: AsyncSession, user_id: uuid.UUID,
    sort: str = "hot", page: int = 1
) -> list[Post]:
    """ホーム Feed（Join 済みの投稿一覧）"""
    from app.comments.models import Comment

    offset = (page - 1) * PAGE_SIZE

    query = (
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .join(SubredditMember, SubredditMember.subreddit_id == Post.subreddit_id)
        .where(SubredditMember.user_id == user_id)
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .limit(PAGE_SIZE)
        .offset(offset)
    )
    query = _apply_sort(query, sort)

    result = await db.execute(query)
    rows = result.all()

    posts = []
    for post, comment_count in rows:
        post.comment_count = comment_count
        posts.append(post)
    return posts


async def list_user_posts(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1
) -> list[Post]:
    """ユーザーの投稿一覧（プロフィールページ用）"""
    from app.comments.models import Comment

    offset = (page - 1) * PAGE_SIZE

    result = await db.execute(
        select(Post, func.count(Comment.id).label("comment_count"))
        .outerjoin(Comment, Comment.post_id == Post.id)
        .where(Post.author_id == user_id)
        .group_by(Post.id)
        .options(selectinload(Post.author), selectinload(Post.subreddit))
        .order_by(Post.inserted_at.desc())
        .limit(PAGE_SIZE)
        .offset(offset)
    )
    rows = result.all()

    posts = []
    for post, comment_count in rows:
        post.comment_count = comment_count
        posts.append(post)
    return posts


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
        .order_by(Post.hot_score.desc())
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
        return query.order_by(Post.inserted_at.desc())
    return query.order_by(Post.hot_score.desc())   # デフォルトは hot


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
        await _create_vote(db, user_id, "post", post_id, value)
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
    return vote


async def _update_post_score(
    db: AsyncSession, post: Post, diff: int
) -> None:
    new_score = post.score + diff
    new_hot = Post.compute_hot_score(new_score, post.inserted_at)

    await db.execute(
        update(Post)
        .where(Post.id == post.id)
        .values(score=new_score, hot_score=new_hot)
    )
    # Python オブジェクトも更新する
    post.score = new_score
    post.hot_score = new_hot


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
```

**読み解き**

`selectinload` は関連データを効率的に取得します。

```python
select(Post).options(
    selectinload(Post.author),    # author を別クエリで一括取得
    selectinload(Post.subreddit)  # subreddit を別クエリで一括取得
)
```

`selectinload` を使わないと N+1 問題が発生します。投稿10件を取得したとき、各投稿の `author` にアクセスするたびにクエリが走り、合計11回のクエリになります。`selectinload` なら2回のクエリで済みます。

投票の4パターンはElixir版と全く同じロジックです。

```python
if existing_vote is None:           # パターンA: 新規
elif existing_vote.value == value:  # パターンB: 取り消し
else:                               # パターンC: 変更
```

パターンB・C で `_update_post_score` と `update_karma` に渡しているのは、「新しいスコア」ではなく「変化量（diff）」です。新規なら `+1`、取り消しなら `-1`、逆方向への変更なら `-2` または `+2`、と変化量に直すことで、3つのパターンを同じ関数の呼び出しで処理できます。「今の値をいくつにするか」ではなく「いくつ動かすか」で考えるのが、投票処理の肝です。

`hot_score` は第3章でモデルに定義した `Post.compute_hot_score(score, inserted_at)` で計算します。中身は、スコアの大きさを `log10` で圧縮したものと、投稿時刻の新しさを足し合わせた値です。スコアの桁が1つ増えるごとに `+1`、投稿時刻が約12.5時間新しいごとに `+1` される計算で、「評価が高い投稿」と「新しい投稿」の両方を上に出すための指標です。`_update_post_score` は投票のたびにスコアと一緒に `hot_score` も計算し直します。時刻の部分は投稿時刻で決まるため、同じスコアなら新しい投稿ほど大きな値になり、「Hot」での並び替えは、この値を大きい順に並べるだけになります。

---

後編では Comments Service と Reports Service を実装します。
