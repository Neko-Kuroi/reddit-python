# 第3章　SQLAlchemy Models（後編）

---

## 3-7　Post モデル

```python
# app/posts/models.py
import uuid
import math
from typing import ClassVar
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, UUID, ForeignKey, DateTime, func, text
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
        """Reddit オリジナルのアルゴリズムをシンプルにしたもの"""
        epoch = datetime(2005, 12, 8, 7, 46, 43, tzinfo=timezone.utc)
        order = math.log10(max(abs(score), 1))
        seconds = (inserted_at - epoch).total_seconds()
        return order + seconds / 45_000

    def __repr__(self) -> str:
        return f"<Post {self.title[:30]}>"
```

**読み解き**

`votes` のアソシエーションは特殊な書き方が必要です。`target_type` と `target_id` のポリモーフィック設計のため、通常の `ForeignKey` が使えません。

```python
votes: Mapped[list["Vote"]] = relationship(
    "Vote",
    primaryjoin="and_(Vote.target_type=='post', "
                "foreign(Vote.target_id)==Post.id)",
    viewonly=True
)
```

`viewonly=True` は読み取り専用のアソシエーションです。投票の追加・削除は直接 `Vote` モデルを操作します。

`comment_count` は DB のカラムではなく Python 側で後からセットするフィールドです。Elixir版の `virtual: true` フィールドに相当します。

カラムではない属性は `ClassVar` で宣言し、実体は `__init__` でインスタンスごとに初期化します。クラス属性に既定値を直接置く書き方（`comment_count: int = 0`）は、SQLAlchemy のマッピング対象と紛らわしいうえ、値がミュータブルな場合は全インスタンスで共有されてしまうため避けます（3-9 の `children` も同じ理由でこの形にしています）。

---

## 3-8　Post の Pydantic スキーマ

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

**読み解き**

`@model_validator(mode="after")` は全フィールドが検証された後に実行されます。`type` の値によって `body` または `url` の必須チェックを切り替える場合など、複数フィールドをまたぐバリデーションに使います。Elixir版の `validate_by_type/1` に相当します。

`Literal["text", "link"]` は `type` フィールドが `"text"` または `"link"` のみであることを型レベルで保証します。

---

## 3-9　Comment モデル

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

**読み解き**

自己参照の `relationship` は `remote_side` を指定する必要があります。

```python
parent: Mapped["Comment | None"] = relationship(
    "Comment",
    back_populates="replies",
    remote_side="Comment.id"  # ← 「id が親側」と明示する
)
```

これがないと SQLAlchemy がどちらが親でどちらが子かを判断できません。

`children` は DB のカラムではなく、ツリー構築のときに Python 側でセットする属性です。3-7 の `comment_count` と同じく `ClassVar` 宣言＋ `__init__` でのインスタンス属性化にしています。以前の書き方（`children: list = []` をクラス属性に直接置く）では、リストが全インスタンスで共有され、あるコメントへの追加が他のコメントにも漏れてしまいます。

---

## 3-10　Vote・Report モデル

```python
# app/posts/models.py に追加

class Vote(Base):
    __tablename__ = "votes"

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

**読み解き**

`Report` モデルも他のモデルと同じく、ファイル先頭で必要な import をすべて書きます（`Base` や `Mapped` は import しなければ使えません）。

報告理由の候補リスト（`VALID_REASONS`）はモデルには置きません。第4章の Reports Service 側に正本を1つだけ置き、モデル・テンプレートはそちらを参照する形にします（同じリストを複数箇所に書くと、変更したときの同期漏れが起きるためです）。

なお、この節の `Vote` は、3-7 で作った `app/posts/models.py` の末尾への **追加** です。`Post` と `Vote` を合わせたファイルの完成形は、全コード付録 2 に収録しています。

---

## 動作確認（この章の仕上げ）

この章の終わりに、プロジェクトのフォルダで Python を使って次を確かめてください。前提は、第1章の仮想環境が有効になっていることです（DB 接続までは不要です）。

- [ ] `python -c "import app.accounts.models, app.communities.models, app.posts.models, app.comments.models, app.reports.models"` がエラーなく終わる（import の不足が無いこと）
- [ ] `python -c "from app.database import Base; import app.posts.models; print(sorted(Base.metadata.tables))"` で、7つのテーブル名が表示される
- [ ] `UserCreate(username="ab", email="bad", password="short")` を作ろうとすると、検証エラーで問題が一覧になって返る（名前の長さ、メールの形式、パスワードの長さ）
- [ ] `PostCreate(title="t", type="text")`（本文なし）が「テキスト投稿には本文が必要です」で弾かれ、`body` を付けると通る
- [ ] 本文が 40,001 字の `PostCreate` が、長さの検証で弾かれる

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| モデルの読み込みで `NameError: name 'Base' is not defined` のような、名前が無いというエラーが出る | ファイル先頭の import が不足している（使う名前を読み込んでいない） | そのファイルで使う名前（`Base`、`Mapped`、`func` など）が全て import されているか確認する。他のモデルファイルの import と見比べると早い |
| 主キーの既定値まわりで、テーブル作成や保存が失敗する | `server_default` に SQL の式をただの文字列で書いている | `text("uuid_generate_v4()")` の形で書く（3-3 の読み解きのとおり、文字列のままだと SQL 側で文字列そのものとして解釈されます） |
| `EmailStr` の読み込みで「email-validator is not installed」と出る | 依存関係に email-validator が入っていない | 第1章の `requirements.txt` のとおり `email-validator` を入れる |
| あるコメントの `children` に足したはずの返信が、他のコメントにも現れる | `children` をクラス属性のリストとして全インスタンスで共有している | 3-9 の形（`ClassVar` で宣言し、`__init__` でインスタンスごとに初期化）に直す |

---

## 確認問題

1. SQLAlchemy モデルと Pydantic スキーマの役割分担を、User の登録を例に説明してください（パスワードは、どちらのどこに現れて、どこに現れませんか）。
2. `username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)` を読み解いてください。`Mapped[str]` の部分と、`mapped_column(...)` の部分は、それぞれ何を決めていますか。
3. `Post.comment_count` と `Comment.children` は、DB のカラムではないのにクラスに書かれています。なぜですか。また、`ClassVar` で宣言し、実体を `__init__` で初期化する形にするのはなぜですか。
4. `PostCreate` で、本文の長さのチェックは `@field_validator`、`type` に応じた必須チェックは `@model_validator` に分かれています。なぜですか。

---

## まとめと次章へのつながり

この章では以下を完了しました。

```
✅ SQLAlchemy 2.0 の Mapped 型付きマッピングを理解した
✅ TimestampMixin で共通フィールドを共有した
✅ 7つのモデルを実装した
✅ Pydantic スキーマでバリデーションを定義した
✅ @model_validator で複数フィールドをまたぐ検証を実装した
```

**Elixir版との重要な比較**

```
Elixir版
  スキーマ + チェンジセットが1ファイル
  バリデーションはパイプラインで書く

FastAPI版
  SQLAlchemy Model  → テーブル定義・アソシエーション
  Pydantic スキーマ → バリデーション・型定義
  役割を分けることでそれぞれが明確になる
```

次の章ではこれらのモデルを使って**ビジネスロジック（Service 層）**を実装します。この章で作ったスキーマの検証は、そこで「入口で弾く」ための道具として使われます。

---

## 確認問題の答え

1. モデルは「保存されるデータの形」を決め、パスワードはハッシュ化した `password_hash` として持ちます。Pydantic スキーマは用途ごとの入出力の形で、登録入力の `UserCreate` には平文の `password` が現れますが、出力の `UserResponse` にはパスワードもハッシュも現れません。長さや形式の検証は、入力側のスキーマが担います。
2. `Mapped[str]` は Python 側の型の宣言で、「この属性は文字列で、空（NULL）にはならない」ということを型として表します。`mapped_column(...)` は DB 側の定義で、列の型（`String(20)`）、ユニーク制約、NULL 不可を指定します。SQLAlchemy 2.0 の記法では、この2つを並べて1行で書きます。
3. どちらも「DB には保存せず、Python 側で後からセットする値」だからです（`comment_count` はクエリでの集計結果、`children` はツリー構築の結果。Elixir 版の virtual フィールドに相当します）。クラス属性に既定値をそのまま置くと、リストのような書き換え可能な値は全インスタンスで共有されてしまいます。`ClassVar` は「これはカラムではない」という宣言で、実体を `__init__` でインスタンスごとに作ることで共有を避けています。
4. 本文の長さは、そのフィールド1つだけを見れば判定できるため `@field_validator` で足ります。一方「text なら本文が必須、link なら URL が必須」は、`type` と他のフィールドを一緒に見なければ判定できません。全フィールドの検証が終わった後に動く `@model_validator` が必要なのは、そのためです。
