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

`hot_score` は第3章でモデルに定義した式と同じ計算を、投票時は SQL の中でも行います。スコアの絶対値を `log10` で圧縮し、正負の符号を掛けたものと、投稿時刻の新しさを足し合わせます。スコアの桁が1つ増えるごとに大きさは `+1` され、正なら上、負なら下へ動きます。投稿時刻が約12.5時間新しいごとにも `+1` されるため、「評価が高い投稿」と「新しい投稿」の両方を上に出す指標になります。

同時実行への備えも、この節の大切な点です。新規投票では、まず Vote を `flush` して一意インデックスに競合を判定させます。同じ票が並行して届いた片方は `IntegrityError` を受け取り、スコアを加算せず現在の投稿を返します。競合が無ければ、`_update_post_score` が `Post.score + diff` という DB 側の式でスコアを更新し、同じ SQL で符号付きの `hot_score` も計算します。Python 側で古いスコアを読んで絶対値を書き戻す形ではないため、別の利用者の投票を上書きして消すことがありません。

一覧では、並びの第1キーだけでは同点の順序が決まりません。Hot では `hot_score` の後に、New では投稿時刻の後に、必ず `Post.id` を第2キーとして付けます。また Service は1ページ分より1件多く読み、`has_more` も一緒に返します。ちょうど25件だけのときに、実際には無い次ページをあるものとして表示しないためです。

---

後編では Comments Service と Reports Service を実装します。
