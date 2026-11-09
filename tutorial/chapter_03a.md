# 第3章　SQLAlchemy Models（前編）

---

### この章で学ぶこと

- 作るもの: 全モデル共通の土台（TimestampMixin）、User・Subreddit・SubredditMember のモデルと、User・Subreddit の Pydantic スキーマ（後編で Post・Comment・Vote・Report を作ります）
- 学ぶ考え方: SQLAlchemy 2.0 の `Mapped` 記法（型ヒントでカラムを表す書き方）、役割分担（テーブル定義はモデル、入力の検証は Pydantic スキーマ）、関連（relationship）の張り方

### 前提

- 第2章が終わっていること（7つのテーブルと、その列の形が決まっていること）
- 第1章の DB 接続（`app/database.py` の `Base`）が用意できていること

### 全体の中での位置

この章は **Data 層** の章です。第2章で決めたテーブルの形を、Python のクラスとして書き表します。入力の形の検証は、Data 層と並ぶ Pydantic スキーマが担当します。第4章の Service 層は、この章のモデルとスキーマを使って処理を書きます。

なお、この章のモデル・スキーマの全文は、巻末の全コード付録 2（appendix_code_02）に収録しています。

---

## 3-1　SQLAlchemy Models とは

SQLAlchemy Models はテーブルと Python クラスを対応させる仕組みです。Elixir の Ecto スキーマに相当します。

```
Elixir版                    FastAPI版
────────────────────────────────────────────
Ecto スキーマ           →   SQLAlchemy Model
チェンジセット          →   Pydantic スキーマ
belongs_to / has_many   →   relationship()
virtual フィールド       →   @property または Pydantic フィールド
```

**Elixir版との重要な違い**

Elixir では1つのファイル（スキーマ）がテーブル定義・バリデーション・アソシエーションを全て担当しました。FastAPI では役割を2つに分けます。

```
SQLAlchemy Model  ← テーブル定義・アソシエーション
Pydantic スキーマ ← バリデーション・入出力の型定義
```

**読み解き**

なぜ検証をモデルと分けるのかを、先に押さえておきます。モデルは「保存されるデータの形」を決めるもので、DB の都合（型・制約・関連）で書きます。一方、入力の検証は「外から来た値が、用途の決まりに合っているか」を見るもので、用途ごとに変わります。同じ User でも、登録の入力（パスワードが必要）と表示用の出力（パスワードは出さない）では形が違うため、検証と入出力の形は用途ごとに Pydantic スキーマで分けて持つのが自然です。この分担が、この章全体の背骨になります。

---

## 3-2　ベースモデルの設定

全モデルで共通の設定を `app/database.py` に追加します。

```python
# app/database.py に追加
import uuid
from sqlalchemy import DateTime, func
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime

class TimestampMixin:
    """inserted_at / updated_at を自動管理するミックスイン"""
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
```

**読み解き**

Mixin（ミックスイン）は、「共通の部品を、継承で各クラスに混ぜ込む」ための小さなクラスです。`inserted_at` / `updated_at` の定義を全モデルに繰り返し書く代わりに、`TimestampMixin` に1度だけ書き、各モデルが `class User(Base, TimestampMixin)` のように受け継ぎます。`server_default=func.now()` は「保存時に DB の現在時刻を入れる」という DB 側の既定値、`onupdate=func.now()` は「行が更新されるたびに DB 側で時刻を入れ直す」という指定です。なお、この時点で `app/database.py` は、1-4 の内容にこの Mixin を足した状態になります（ファイルの完成形は全コード付録 1 にあります）。

---

## 3-3　User モデル

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

**読み解き**

`Mapped[str]` は SQLAlchemy 2.0 の型付きマッピングです。Python の型ヒントで DB のカラム型を表現します。

```python
# 古い書き方（SQLAlchemy 1.x）
username = Column(String(20), unique=True, nullable=False)

# 新しい書き方（SQLAlchemy 2.0）
username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
```

新しい書き方は型安全性が高く、IDE の補完も効きます。

`relationship()` は Ecto の `belongs_to` / `has_many` に相当します。`back_populates` で双方向の参照を設定します。

なお、主キーの `server_default` は `text("uuid_generate_v4()")` のように SQL 式の形で書きます。ただの文字列で書くと SQL 側で文字列リテラルとして解釈されてしまい、UUID を生成する既定値として機能しません（第2章のマイグレーション側の書き方と揃えています）。以降のモデルもすべてこの形に統一します。

---

## 3-4　User の Pydantic スキーマ

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
        return v

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

**読み解き**

`EmailStr` は Pydantic の型で、メールアドレスの形式を自動的に検証します。

`@field_validator` は Ecto のチェンジセットの `validate_format` に相当します。

`model_config = {"from_attributes": True}` は SQLAlchemy の Model オブジェクトを Pydantic モデルに変換できるようにする設定です。

```python
user = await db.get(User, user_id)
response = UserResponse.model_validate(user)  # Model → Pydantic
```

検証の置き場所にも注目してください。`UserCreate` は「登録の入口から来た値」を受け取る専用の形で、DB のモデルとは独立しています。入口で弾かれた値は、Service 層や DB に届く前にエラーとして返ります（受け取りの流れは第5章の Router で完成します）。Elixir 版でチェンジセットが担っていた「入口での検証」の役割を、こちらでは Pydantic スキーマが担う、という対応です。

---

## 3-5　Subreddit モデル

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

**読み解き**

`Mapped[str | None]` は `nullable=True` に対応します。Python の `Optional[str]` と同じ意味です。

`SubredditMember` は `TimestampMixin` を使わず `inserted_at` だけを持ちます。更新日時は不要だからです。Elixir版の `timestamps(updated_at: false)` に相当します。

---

## 3-6　Subreddit の Pydantic スキーマ

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
        return v

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

**読み解き**

3-4 と見比べると、Pydantic の検証の型が見えてきます。フィールド1つだけを見る検証は `@field_validator` に書き、通れば値をそのまま返し、駄目なら `ValueError` を投げます。投げられたエラーは Pydantic が集めて、呼び出し側に「どのフィールドが、なぜ駄目か」の一覧として返します。`SubredditResponse` のような出力側のスキーマに検証が無く、形の宣言だけがあるのは、入口と出口で役割が違うためです（3-1 の読み解きを参照）。

---

後編では Post・Comment・Vote・Report モデルを実装します。
