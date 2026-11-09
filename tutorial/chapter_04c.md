# 第4章　ビジネスロジック（Service 層）後編

---

## 4-6　Comments Service

```python
# app/comments/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.exc import IntegrityError
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
        try:
            await db.flush()   # 一意制約の競合はここで検出する
        except IntegrityError as e:
            if not _is_vote_unique_violation(e):
                raise
            # 同じ投票が並行して届いた場合は、先に保存された票が正本。
            await db.rollback()
            current_result = await db.execute(
                select(Comment)
                .where(Comment.id == comment_id)
                .options(selectinload(Comment.author))
            )
            current_comment = current_result.scalar_one_or_none()
            if current_comment is None:
                raise ValueError("コメントが見つかりません")
            return current_comment
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


def _is_vote_unique_violation(error: IntegrityError) -> bool:
    original = getattr(error, "orig", None)
    diagnostic = getattr(original, "diag", None)
    constraint = getattr(diagnostic, "constraint_name", None)
    return constraint == "ix_votes_unique" or "ix_votes_unique" in str(original)


async def _update_comment_score(
    db: AsyncSession, comment: Comment, diff: int
) -> None:
    # score は DB 側で差分加算し、同時投票でも更新を失わない
    result = await db.execute(
        update(Comment)
        .where(Comment.id == comment.id)
        .values(score=Comment.score + diff)
        .returning(Comment.score)
    )
    comment.score = result.scalar_one()


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
```

**読み解き**

Elixir版と全く同じアルゴリズムを Python で実装しています。

```python
def _build_tree(comments):
    # Step1: parent_id ごとにグループ化
    by_parent = {}
    for comment in comments:
        key = comment.parent_id   # None がトップレベル
        by_parent.setdefault(key, []).append(comment)

    # Step2: 再帰でツリーを組み立てる
    def build_children(parent_id):
        children = by_parent.get(parent_id, [])
        for child in children:
            child.children = build_children(child.id)  # 再帰！
        return children

    return build_children(None)   # None（トップレベル）から開始
```

なぜ再帰を使うのかというと、コメントの返信は「何段重なるか」が分からない入れ子構造だからです。「2段まで」「3段まで」と決め打ちでループを書くと、それより深い返信が来たときに組み立てられません。再帰は「子を集める」という同じ処理を、深さの分だけ繰り返し適用する書き方で、このような形のデータに向いています。

再帰で大切なのは「終わりの条件」です。ここでは `by_parent` にキーが無い（＝子が無い）ときに空のリストが返り、そこで掘り下げるのが止まります。トップレベルは `parent_id` が `None` のグループなので、開始点は `build_children(None)` です。

もう1つ、この設計の肝は「DB への問い合わせは最初の1回だけ」という点です。コメントごとに「その子はどれか」を DB へ聞きに行くと、コメントの数だけクエリが増えてしまいます（中編の N+1 の話と同じです）。先に全件を取ってメモリ上で組み立てることで、コメントが何件でもクエリは1回で済みます。`children` は DB のカラムではなく、この組み立てのときにインスタンスへ付ける属性です（第3章の `comment_count` と同じ扱い）。

コメント投票も投稿投票と同じ順序で競合に備えます。新しい票は先に `flush` して一意インデックスで重なりを判定し、並行した同じ票の片方はスコアを加算せず現在のコメントを返します。スコアそのものは `Comment.score + diff` と DB 側で差分加算するため、別々の利用者が同時に投票しても更新が失われません。

---

## 4-7　Reports Service

```python
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
```

**読み解き**

Reports Service は小さいですが、「Service の入口で検証を済ませる」例になっています。報告理由が `VALID_REASONS` にあるか、`target_type` が `"post"` か `"comment"` か、対象が存在するか、対象の作者は誰で「自分のコンテンツは報告できない」に当たらないか、といった確認はすべてここで行います。Router 側はフォームの値を受け取って渡すだけで、ルールは持ちません。

対象の存在確認は、`_get_author_id` が `None` を返したかどうかで判定します。対象がすでに削除されている場合などは作者が取得できないため、「報告対象が見つかりません」の `ValueError` にして、存在しない対象への報告が保存されないようにしています。

`_get_author_id` のようにアンダースコアで始まる関数は、「このファイルの中だけで使う補助」という印です。付録の関数一覧でも「（内部）」と付けて区別しています。外から呼ぶ関数と内部の補助を分けることで、Service の「表の顔」がどれかを一目で分かるようにしています。

---

## 動作確認（この章の仕上げ）

前提: 第2章のマイグレーションが適用済みで、PostgreSQL に接続できること。画面（Router）はまだ無いので、Service を直接呼んで確かめます。プロジェクトのフォルダで、次の内容を `check_ch4.py` として保存し、`python check_ch4.py` で実行してください（確認が終わったら消して構いません）。

```python
import asyncio
from app.database import AsyncSessionLocal
from app.accounts.schemas import UserCreate
from app.accounts import services as accounts
from app.communities.schemas import SubredditCreate
from app.communities import services as communities

async def main():
    async with AsyncSessionLocal() as db:
        alice = await accounts.create_user(db, UserCreate(
            username="alice", email="alice@example.com", password="password123"))
        await db.commit()
        print("登録:", alice.username)

        ok = await accounts.authenticate_user(db, "alice@example.com", "password123")
        ng = await accounts.authenticate_user(db, "alice@example.com", "wrong-password")
        print("認証 成功/失敗:", ok is not None, ng is None)

        sub = await communities.create_subreddit(
            db, SubredditCreate(name="elixir", description="Elixirの話題"), alice.id)
        await db.commit()
        print("モデレーター:", await communities.is_moderator(db, alice.id, sub.id))

asyncio.run(main())
```

- [ ] 上のスクリプトがエラーなく終わり、「登録: alice」「認証 成功/失敗: True True」「モデレーター: True」と表示される
- [ ] 同じスクリプトをもう一度実行すると、`create_user` で「すでに使われています」の `ValueError` になる（重複チェックが働いている）
- [ ] 投稿を作り、別のユーザーが `vote_post` で `+1` → スコア 1、もう一度 `+1` → スコア 0（取り消し）、`-1` → スコア -1 になる（上のスクリプトに足して確認する）
- [ ] 自分の投稿への `vote_post` が `ValueError`（自分の投稿には投票できません）になる
- [ ] コメントに返信を付けると、`list_comments` の結果で返信が親の `children` に入っている
- [ ] 自分の投稿への `create_report` が `ValueError`（自分のコンテンツは報告できません）になる
- [ ] 存在しない投稿 ID への `create_report` が `ValueError`（報告対象が見つかりません）になり、報告が保存されない

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| Service を呼んだのに何も起きず、`coroutine ... was never awaited` という警告が出る | `await` の付け忘れ。`async def` の関数は、呼ぶだけでは実行されない | 呼び出し側に `await` を付ける（4-2 の読み解き） |
| 関連データ（`author` など）に触ると `MissingGreenlet` というエラーになる | 非同期の SQLAlchemy では、読み込んでいない関連をその場で読みに行くこと（遅延読み込み）ができない | 取得のときに `selectinload` で先に読み込んでおく（4-5 の読み解き）。一覧の取得では特に忘れやすい |
| Service で `flush` したのに、他の接続からはデータが見えない | `flush` は確定（commit）ではない。コミットは `get_db` がリクエストの終わりに行う | Service の中では `commit` しないのが本書の約束。動作確認のスクリプトのように自分でセッションを扱う場合は、自分で `commit` する |
| 存在しない `parent_id` で返信しようとすると、DB の外部キーエラーで落ちる | 返信先の確認をせずに保存しようとしている | 4-6 の `create_comment` のように、Service の中で先に存在と所属を確認し、`ValueError` に変換する |
| 報告が「報告対象が見つかりません」になる | 報告しようとした投稿・コメントが、すでに削除されるなどして存在しない | 仕様どおりの動作。存在する対象を報告し直す（`create_report` は対象の存在も入口で確認している） |
| 投票のたびにスコアが少しずつずれる | 「取得して +1 して保存」という書き方で、同時リクエストと競合している | `update()` で DB 側に計算させる（`update_karma` の形）。スコア側は差分（diff）を渡す設計にする |

---

## 確認問題

1. Router に直接ビジネスロジックを書かず、Service 層に分ける理由を2つ挙げてください。
2. `create_subreddit` で `flush()` を2回呼んでいます。1回目（Subreddit を追加した直後）の `flush` が必要なのはなぜですか。
3. すでに `+1` で投票した投稿に、もう一度 `+1` の `vote_post` を呼ぶと、スコアと作者の Karma はどうなりますか。続けて `-1` を呼んだ場合はどうなりますか。
4. `_build_tree` は、DB へ追加の問い合わせをせずにツリーを組み立てられます。なぜですか。また、コメントが1件も無いとき、何を返しますか。
5. `update_karma` が「ユーザーを取得して +1 して保存」ではなく、`update()` で DB 側に計算させているのはなぜですか。

---

## まとめと次章へのつながり

この章では以下を完了しました。

```
✅ Service 層の役割を理解した（Context との対応）
✅ async/await の基本パターンを学んだ
✅ Accounts Service（登録・認証・Karma）
✅ Communities Service（Subreddit・Join/Leave）
✅ Posts Service（投稿・投票・検索）
✅ Comments Service（コメント・ツリー・投票）
✅ Reports Service（報告）
```

**この章の重要なポイント**

```
selectinload で N+1 問題を防ぐ
update() で DB レベルの直接更新（Karma・score）
flush() でコミット前に ID を確定させる
select(exists()) で効率的な存在確認
_build_tree で1クエリ→メモリ上でツリー構築
```

次の章では認証システムを実装します。Cookie セッション・itsdangerous・passlib を組み合わせてセキュアなログインを実現します。この章で作った Service は、第5章の認証 Router と第6章の各 Router から呼ばれます。特に「成功したら値、失敗したら例外」という約束は、Router 側のエラー表示の前提になります。

---

## 確認問題の答え

1. 同じルールを複数の入口（複数の画面や、将来の API）から使い回せること、そして Service はただの関数なので、HTTP リクエストを作らなくても呼び出してテストできることです（ほかに、Router 側が「受け取る・呼ぶ・返す」だけになって見通しがよくなることもあります）。
2. 作成者を moderator として登録するには `subreddit.id` が必要ですが、ID は DB に送って初めて確定します。1回目の `flush` で ID を確定させてからでないと、参加記録（SubredditMember）を作れません。
3. もう一度 `+1` を呼ぶと、同じ方向への再投票として取り消しになり、スコアも Karma も `-1` されて元の状態に戻ります。続けて `-1` を呼ぶと、新規の `-1` 投票として扱われ、スコアも Karma もさらに `-1` されます（なお、`+1` の状態から直接 `-1` を呼んだ場合は「逆方向への変更」で、差分 `-2` が一度に適用されます）。
4. 投稿の全コメントを最初の1回のクエリで取得し、`parent_id` でグループ化した辞書（`by_parent`）を持っているからです。子はその辞書から引けるので、追加の問い合わせは要りません。コメントが無いときは、トップレベルのグループも空なので、空のリスト `[]` を返します。
5. 同時に複数のリクエストが来たときの競合を防ぐためです。「取得して +1 して保存」だと、読み取ってから書き込むまでの間に別のリクエストが値を変えていると、上書きしてしまいます。DB 側で「現在の値 + amount」と計算させれば、リクエスト同士がぶつかっても正しく加算されます。
