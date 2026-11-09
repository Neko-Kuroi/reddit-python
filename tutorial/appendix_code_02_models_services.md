# 全コード付録 2　モデルとサービス（Data 層と Service 層）

> **このファイルは自動生成です。** 生成スクリプト `~/workspace/reddit_clone_audit/generate_code_appendix_py.py` が、
> 正本のコードファイル（`~/workspace/reddit_clone_python/` 内）から全文を機械的に転記して作りました。
> **正本はコードファイルそのもの**であり、この付録は「すべてのコードがチュートリアル側に収録されている」
> ことを保証するための再録です。コードを直すときは正本を直し、この付録は再生成してください。
>
> 対応する章: 第3章（モデルとスキーマ）、第4章（Service）

---

## app/accounts/models.py

対応: 第3章。正本: `app/accounts/models.py`

```python
# app/accounts/models.py
import uuid
from sqlalchemy import String, Integer, UUID, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    post_karma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_karma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # アソシエーション
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="author", foreign_keys="Post.author_id"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="author"
    )
    subreddit_members: Mapped[list["SubredditMember"]] = relationship(
        "SubredditMember", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"
```

## app/accounts/schemas.py

対応: 第3章。正本: `app/accounts/schemas.py`

```python
# app/accounts/schemas.py
import uuid
from pydantic import BaseModel, EmailStr, field_validator
import re

class UserCreate(BaseModel):
    """ユーザー登録フォームのバリデーション"""
    username: str
    email: EmailStr
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 20:
            raise ValueError("ユーザー名は3〜20文字にしてください")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("ユーザー名は英数字とアンダースコアのみ使用できます")
        return v.lower()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("パスワードは8文字以上にしてください")
        return v

class UserResponse(BaseModel):
    """ユーザー情報のレスポンス"""
    id: uuid.UUID
    username: str
    post_karma: int
    comment_karma: int

    model_config = {"from_attributes": True}  # SQLAlchemy Model から変換できる
```

## app/communities/models.py

対応: 第3章。正本: `app/communities/models.py`

```python
# app/communities/models.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, UUID, ForeignKey, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class Subreddit(Base, TimestampMixin):
    __tablename__ = "subreddits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    name: Mapped[str] = mapped_column(String(21), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    # アソシエーション
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="subreddit")
    members: Mapped[list["SubredditMember"]] = relationship(
        "SubredditMember", back_populates="subreddit"
    )

    def __repr__(self) -> str:
        return f"<Subreddit r/{self.name}>"


class SubredditMember(Base):
    __tablename__ = "subreddit_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    subreddit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subreddits.id", ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # アソシエーション
    user: Mapped["User"] = relationship("User", back_populates="subreddit_members")
    subreddit: Mapped["Subreddit"] = relationship(
        "Subreddit", back_populates="members"
    )

    def __repr__(self) -> str:
        return f"<SubredditMember user={self.user_id} subreddit={self.subreddit_id}>"
```

## app/communities/schemas.py

対応: 第3章。正本: `app/communities/schemas.py`

```python
# app/communities/schemas.py
import uuid
import re
from pydantic import BaseModel, field_validator

class SubredditCreate(BaseModel):
    name: str
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 21:
            raise ValueError("コミュニティ名は3〜21文字にしてください")
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("英数字とアンダースコアのみ使用できます")
        return v.lower()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v and len(v) > 500:
            raise ValueError("説明は500文字以内にしてください")
        return v

class SubredditResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}
```

## app/posts/models.py

対応: 第3章（Vote は 3-10 で追加）。正本: `app/posts/models.py`

```python
# app/posts/models.py
import uuid
import math
from typing import ClassVar
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, UUID, ForeignKey, DateTime, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)   # "text" | "link"
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hot_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    subreddit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subreddits.id", ondelete="CASCADE"),
        nullable=False
    )

    # アソシエーション
    author: Mapped["User"] = relationship(
        "User", back_populates="posts", foreign_keys=[author_id]
    )
    subreddit: Mapped["Subreddit"] = relationship(
        "Subreddit", back_populates="posts"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(
        "Vote",
        primaryjoin="and_(Vote.target_type=='post', "
                    "foreign(Vote.target_id)==Post.id)",
        viewonly=True
    )

    # comment_count は DB に持たない（クエリで集計して Python 側でセットする）
    # カラムではないので ClassVar で宣言し、実体は __init__ で
    # インスタンス属性として初期化する
    comment_count: ClassVar[int]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.comment_count = 0

    @staticmethod
    def compute_hot_score(score: int, inserted_at: datetime) -> float:
        """Reddit の Hot アルゴリズム（スコアの符号を保持する）"""
        epoch = datetime(2005, 12, 8, 7, 46, 43, tzinfo=timezone.utc)
        sign = (score > 0) - (score < 0)
        order = sign * math.log10(max(abs(score), 1))
        seconds = (inserted_at - epoch).total_seconds()
        return order + seconds / 45_000

    def __repr__(self) -> str:
        return f"<Post {self.title[:30]}>"


# === appended from chapter_03b.md block 5 ===
# app/posts/models.py に追加

class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        Index(
            "ix_votes_unique",
            "user_id", "target_type", "target_id",
            unique=True
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)       # +1 | -1
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "post"|"comment"
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
```

## app/posts/schemas.py

対応: 第3章。正本: `app/posts/schemas.py`

```python
# app/posts/schemas.py
import uuid
from typing import Literal
from pydantic import BaseModel, field_validator, model_validator

class PostCreate(BaseModel):
    title: str
    type: Literal["text", "link"]
    body: str | None = None
    url: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if len(v) < 1 or len(v) > 300:
            raise ValueError("タイトルは1〜300文字にしてください")
        return v

    @field_validator("body")
    @classmethod
    def validate_body(cls, v: str | None) -> str | None:
        # 原典 Elixir 版の仕様に合わせ、本文は最大 40,000 文字
        if v is not None and len(v) > 40_000:
            raise ValueError("本文は40,000文字以内にしてください")
        return v

    @model_validator(mode="after")
    def validate_by_type(self) -> "PostCreate":
        """type に応じて body または url を必須にする"""
        if self.type == "text" and not self.body:
            raise ValueError("テキスト投稿には本文が必要です")
        if self.type == "link":
            if not self.url:
                raise ValueError("リンク投稿には URL が必要です")
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("URL は http:// または https:// で始まる必要があります")
        return self

class PostResponse(BaseModel):
    id: uuid.UUID
    title: str
    type: str
    body: str | None
    url: str | None
    score: int
    comment_count: int = 0

    model_config = {"from_attributes": True}
```

## app/comments/models.py

対応: 第3章。正本: `app/comments/models.py`

```python
# app/comments/models.py
import uuid
from typing import ClassVar
from sqlalchemy import Text, Integer, UUID, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True  # トップレベルのコメントは None
    )

    # アソシエーション
    author: Mapped["User"] = relationship("User", back_populates="comments")
    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    parent: Mapped["Comment | None"] = relationship(
        "Comment", back_populates="replies", remote_side="Comment.id"
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="parent"
    )

    # ツリー構造用（Python側でセットする）
    # カラムではないので ClassVar で宣言し、実体は __init__ で
    # インスタンス属性として初期化する
    # （クラス属性に list の既定値を置くと全インスタンスで共有されてしまう）
    children: ClassVar[list["Comment"]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.children = []

    def __repr__(self) -> str:
        return f"<Comment {str(self.id)[:8]}>"
```

## app/reports/models.py

対応: 第3章。正本: `app/reports/models.py`

```python
# app/reports/models.py
import uuid
from datetime import datetime
from sqlalchemy import String, UUID, ForeignKey, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    reporter: Mapped["User"] = relationship("User")
```

## app/accounts/services.py

対応: 第4章。正本: `app/accounts/services.py`

```python
# app/accounts/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
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
    # 大文字小文字を区別しないよう、保存前に小文字へそろえる
    username = data.username.lower()
    email = data.email.lower()

    # username と email の重複チェック
    existing = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("このユーザー名またはメールアドレスはすでに使われています")

    user = User(
        username=username,
        email=email,
        password_hash=pwd_context.hash(data.password)
    )
    db.add(user)
    try:
        await db.flush()   # ID を確定させる（commit はしない）
        await db.refresh(user)
    except IntegrityError:
        # 重複チェック後に別のリクエストが先に登録した場合は、
        # DB の一意制約違反を 500 ではなく重複エラーとして返す
        await db.rollback()
        raise ValueError("このユーザー名またはメールアドレスはすでに使われています")
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
    result = await db.execute(select(User).where(User.email == email.lower()))
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
    result = await db.execute(select(User).where(User.username == username.lower()))
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

## app/communities/services.py

対応: 第4章。正本: `app/communities/services.py`

```python
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
```

## app/posts/services.py

対応: 第4章。正本: `app/posts/services.py`

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

## app/comments/services.py

対応: 第4章。正本: `app/comments/services.py`

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

## app/reports/services.py

対応: 第4章。正本: `app/reports/services.py`

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
