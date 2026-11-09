# 第4章　ビジネスロジック（Service 層）前編

---

### この章で学ぶこと

- 作るもの: アプリのルールを実装する Service 層の5ファイル（Accounts / Communities / Posts / Comments / Reports Service）
- 学ぶ考え方: サービス層の設計（Router と Service の分担）、非同期処理（`async` / `await`）、トランザクション（`flush` と `commit` の違い）、存在確認の `exists`、投票を「差分」で処理する考え方、再帰によるツリー構造の組み立て

### 前提

- 第3章までが終わっていること（モデルとスキーマがあり、マイグレーションでテーブルが作られていること）
- 第1章の `get_db`（セッションの世話役）の動きを思い出しておくこと。この章の Service はすべて、そのセッションを受け取って動きます

### 全体の中での位置

この章は **Service 層** そのものを作る章です。3層構造の真ん中にあたり、下の Data 層（第2・3章のテーブルとモデル）を使い、上の Web 層（第5・6章の Router）から呼ばれます。原典（Elixir 版）の Context に相当する層です。

なお、この章で作る Service 5件の全文は、巻末の全コード付録 2（appendix_code_02）に収録しています。

---

## 4-1　Service 層とは

Service 層はアプリのルールを実装するコードです。Elixir版の Context に相当します。

```
FastAPI版の層構造

Router（エンドポイント）
  └─ リクエストを受け取り Service を呼ぶだけ

Service 層
  └─ ルールに従って処理する ← ここ

Model 層
  └─ データを保存するだけ
```

Router に直接ビジネスロジックを書くと、別のエンドポイントで同じ処理が必要になったとき、コードをコピーすることになります。Service 層にまとめることで1箇所の修正で全体に反映されます。

**読み解き**

なぜ Router から分けるのか、理由は3つあります。1つ目は、同じルールを複数の入口から使い回せることです。たとえば「投稿に投票する」処理は、投稿詳細ページからも、将来 API を足したときも、まったく同じルールで動く必要があります。2つ目は、テストのしやすさです。Service は「DB のセッションと値を受け取って、結果を返す」ただの関数なので、HTTP リクエストを作らなくても呼び出して確かめられます（この章の動作確認も、その形で行います）。3つ目は、見通しです。Router 側は「受け取る・Service を呼ぶ・応答を返す」だけにすると、画面まわりの都合とアプリのルールが混ざりません。

分担の目安は、「その判断が HTTP と無関係に成り立つか」です。「自分の投稿には投票できない」は、画面があってもなくても成り立つルールなので Service の仕事です。逆に「未ログインならログインページへ送る」は HTTP の都合なので、Router や第5章の Depends の仕事になります。

---

## 4-2　非同期処理の基本

FastAPI の全ての DB 処理は `async/await` で書きます。

```python
# ❌ 同期処理（FastAPI では使わない）
def get_user(db, user_id):
    return db.query(User).filter(User.id == user_id).first()

# ✅ 非同期処理
async def get_user(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
```

`await` は「この処理が終わるまで待つが、待っている間に他のリクエストを処理できる」という意味です。

**読み解き**

この章の Service 関数は、すべて `async def` で定義し、呼び出し側は必ず `await` を付けて呼びます。`await` を忘れると関数は実行されず、「コルーチン」という実行待ちのオブジェクトが返ってくるだけです（警告が出ることもあります）。「呼んだはずなのに何も起きない」ときは、まず `await` の付け忘れを疑ってください。

---

## 4-3　Accounts Service

```python
# app/accounts/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from passlib.context import CryptContext

from app.accounts.models import User
from app.accounts.schemas import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ----------------------------------------------------------------
# ユーザー登録
# ----------------------------------------------------------------

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """
    ユーザーを登録する。
    パスワードをハッシュ化してから保存する。
    """
    # username と email の重複チェック
    existing = await db.execute(
        select(User).where(
            (User.username == data.username) | (User.email == data.email)
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("このユーザー名またはメールアドレスはすでに使われています")

    user = User(
        username=data.username,
        email=data.email,
        password_hash=pwd_context.hash(data.password)
    )
    db.add(user)
    await db.flush()   # ID を確定させる（commit はしない）
    await db.refresh(user)
    return user


# ----------------------------------------------------------------
# ログイン
# ----------------------------------------------------------------

async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    """
    メールとパスワードでユーザーを認証する。
    失敗理由は曖昧にする（セキュリティ上の理由）。
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        # タイミング攻撃対策：ユーザーが存在しなくてもハッシュ計算を行う
        pwd_context.dummy_verify()
        return None

    if not pwd_context.verify(password, user.password_hash):
        return None

    return user


# ----------------------------------------------------------------
# ユーザー取得
# ----------------------------------------------------------------

async def get_user_by_id(db: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


# ----------------------------------------------------------------
# Karma の更新
# ----------------------------------------------------------------

async def update_karma(
    db: AsyncSession, user_id: uuid.UUID, karma_type: str, amount: int
) -> None:
    """
    Karma を増減する。
    投票されたときに Posts / Comments Service から呼ばれる。
    DB レベルで直接更新することで競合を防ぐ。
    """
    if karma_type == "post":
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(post_karma=User.post_karma + amount)
        )
    elif karma_type == "comment":
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(comment_karma=User.comment_karma + amount)
        )
```

**読み解き**

`await db.flush()` はデータを DB に送りますが、コミットはしません。これにより `user.id` などの自動生成値が確定します。実際のコミットは `get_db` の `yield` の後に行われます。

`pwd_context.dummy_verify()` はタイミング攻撃への対策です。ユーザーが存在しない場合でもハッシュ計算を行い、処理時間を同じにします。Elixir版の `Bcrypt.no_user_verify()` に相当します。

`update(User).values(post_karma=User.post_karma + amount)` は DB レベルで直接 Karma を増減します。「取得して +1 して保存」ではなく DB 側で計算するため、同時リクエストが来ても値がずれません。

もう1つ見ておきたいのは、失敗の伝え方です。`create_user` は重複を見つけると `ValueError` を投げます。Service は「画面にどう表示するか」を知らないので、失敗の理由だけを例外に乗せて呼び出し側へ渡し、表示への変換は Router の仕事にしています（第5章で実際に変換します）。成功したら値、失敗したら例外、という約束が Service 全体で統一されています。

---

## 4-4　Communities Service

```python
# app/communities/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, exists, and_

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
    # 名前の重複チェック
    existing = await db.execute(
        select(Subreddit).where(Subreddit.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"r/{data.name} はすでに存在します")

    # Subreddit を作成
    subreddit = Subreddit(
        name=data.name,
        description=data.description,
        owner_id=owner_id
    )
    db.add(subreddit)
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

    return subreddit


# ----------------------------------------------------------------
# Subreddit の取得
# ----------------------------------------------------------------

async def get_subreddit_by_name(
    db: AsyncSession, name: str
) -> Subreddit | None:
    result = await db.execute(
        select(Subreddit).where(Subreddit.name == name)
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
```

**読み解き**

`select(exists().where(...))` は Elixir の `Repo.exists?()` に相当します。レコード全体を取得せず、存在確認だけを行うため効率的です。

`create_subreddit` では `flush()` を2回呼んでいます。

```python
db.add(subreddit)
await db.flush()   # subreddit.id が確定する
                   # ← この ID が必要なので flush が必要

member = SubredditMember(subreddit_id=subreddit.id, ...)
db.add(member)
await db.flush()
```

トランザクションは `get_db` の `yield` で管理されます。エンドポイントが正常終了すれば `commit`、例外が発生すれば `rollback` が自動的に行われます。

この仕組みのおかげで、`create_subreddit` の途中で失敗しても、「Subreddit だけが作られて、作成者が参加していない」という中途半端な状態は残りません。`flush` は「DB に送って確かめる」段階であって、まだ確定（commit）ではない、という区別が大切です。Service の関数の中では `commit` を呼ばないのが、このアプリの約束になっています。

---

中編では Posts Service の投票ロジックを詳しく説明します。
