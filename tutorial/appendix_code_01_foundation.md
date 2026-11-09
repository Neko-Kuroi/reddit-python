# 全コード付録 1　基盤とマイグレーション（入口・共通部品・Alembic・設定）

> **このファイルは自動生成です。** 生成スクリプト `~/workspace/reddit_clone_audit/generate_code_appendix_py.py` が、
> 正本のコードファイル（`~/workspace/reddit_clone_python/` 内）から全文を機械的に転記して作りました。
> **正本はコードファイルそのもの**であり、この付録は「すべてのコードがチュートリアル側に収録されている」
> ことを保証するための再録です。コードを直すときは正本を直し、この付録は再生成してください。
>
> 対応する章: 第1章（セットアップ）、第2章（マイグレーション）

---

## main.py

対応: 第1章（初版）→ 第5章 → 第6章（完成版）。正本: `main.py`

```python
# main.py（完成版）
from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.csrf import CSRFMiddleware, csrf_protect
from app.accounts.router import router as accounts_router
from app.communities.router import router as communities_router
from app.posts.router import router as posts_router
from app.comments.router import router as comments_router

# csrf_protect を全体の依存性にすると、全ルートの状態変更リクエストが
# CSRF 検証の対象になる（第5章 5-9 を参照）
app = FastAPI(
    title="Reddit Clone",
    debug=settings.DEBUG,
    dependencies=[Depends(csrf_protect)],
)

# トークン発行ミドルウェア（検証は csrf_protect が担当する）
app.add_middleware(CSRFMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Jinja2 の templates とカスタムフィルターは app/templating.py に集約し、
# 全 Router が共有する（第6章 6-15 を参照）

# Router の登録
app.include_router(accounts_router)
app.include_router(communities_router)
app.include_router(posts_router)
app.include_router(comments_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

## app/config.py

対応: 第1章。正本: `app/config.py`

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    SESSION_COOKIE_NAME: str = "session"
    DEBUG: bool = False

    class Config:
        env_file = ".env"

# シングルトンとして使う
settings = Settings()
```

## app/database.py

対応: 第1章（第3章で TimestampMixin を追加）。正本: `app/database.py`

```python
# app/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# 非同期エンジンを作成する
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,   # DEBUG=True のとき SQL をログに出力する
    pool_size=10,
    max_overflow=20
)

# セッションファクトリー
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False   # コミット後もオブジェクトにアクセスできる
)

# 全モデルの基底クラス
class Base(DeclarativeBase):
    pass

# DB セッションを取得する（Depends で使う）
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# === appended from chapter_03a.md block 2 ===
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

## app/dependencies.py

対応: 第1章（準備）→ 第5章（完成）。正本: `app/dependencies.py`

```python
# app/dependencies.py
import uuid

from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import verify_session_token
from app.config import settings

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cookie からトークンを取り出し、現在のユーザーを返す。
    未ログインの場合は None を返す。
    Elixir版の fetch_current_user Plug に相当する。
    """
    from app.accounts.services import get_user_by_id

    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        return None

    user_id = verify_session_token(token)
    if not user_id:
        return None

    # トークンの中身は文字列なので、DB 照合の前に UUID 型へ変換する
    # （DB 側の UUID 型はドライバによっては文字列を受け付けないため）
    try:
        user_uuid = uuid.UUID(user_id)
    except (ValueError, AttributeError, TypeError):
        return None

    return await get_user_by_id(db, user_uuid)


async def require_auth(
    current_user=Depends(get_current_user)
):
    """
    ログインが必要なエンドポイントを保護する。
    未ログインの場合はログインページへリダイレクトする。
    Elixir版の on_mount :require_auth に相当する。
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return current_user


async def redirect_if_authenticated(
    current_user=Depends(get_current_user)
):
    """
    すでにログイン済みのユーザーをホームへリダイレクトする。
    登録・ログインページで使う。
    """
    if current_user is not None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/"}
        )
    return None
```

## app/auth.py

対応: 第5章。正本: `app/auth.py`

```python
# app/auth.py
from itsdangerous import URLSafeTimedSerializer, BadSignature
from fastapi import Response, Request
from app.config import settings

COOKIE_MAX_AGE = 60 * 60 * 24 * 7   # 7日間（秒）

def create_session_token(user_id: str) -> str:
    """user_id を署名してトークンを生成する"""
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    return s.dumps(user_id, salt="session")


def verify_session_token(token: str) -> str | None:
    """
    トークンを検証して user_id を返す。
    無効または期限切れの場合は None を返す。
    """
    s = URLSafeTimedSerializer(settings.SECRET_KEY)
    try:
        return s.loads(token, salt="session", max_age=COOKIE_MAX_AGE)
    except BadSignature:
        return None


def set_session_cookie(response: Response, user_id: str) -> None:
    """レスポンスに Cookie をセットする"""
    token = create_session_token(str(user_id))
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,     # JavaScript からアクセスできない（XSS 対策）
        samesite="lax",    # CSRF 対策
        secure=not settings.DEBUG  # 本番では HTTPS のみ
    )


def clear_session_cookie(response: Response) -> None:
    """Cookie を削除する（ログアウト）"""
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        samesite="lax"
    )
```

## app/csrf.py

対応: 第5章。正本: `app/csrf.py`

```python
# app/csrf.py
"""
CSRF 対策（ダブルサブミットクッキー方式）。

仕組み:
- 発行（CSRFMiddleware）: トークンを持たないリクエストには、
  secrets で生成したランダムなトークンを Cookie にセットする。
  同じトークンはリクエストの Cookie ヘッダーにも注入されるため、
  そのリクエストで描画するテンプレートからも request.cookies 経由で
  参照できる（base.html の meta タグと、フォームの hidden フィールド）。
- 検証（csrf_protect）: 状態を変えるメソッド（POST 等）では、
  「Cookie の値」と「X-CSRF-Token ヘッダー（HTMX 用）または
  フォームの csrf_token フィールド（通常フォーム用）」が
  一致するか、定数時間比較で確認する。不一致・欠落は 403。
  アプリ全体の依存性として main.py で登録する。
"""
import re
import secrets

from fastapi import HTTPException, Request
from starlette.datastructures import MutableHeaders

CSRF_COOKIE_NAME = "csrf_token"
# base.html の既存スクリプトは X-CSRFToken の綴りで送るため、
# ハイフンあり・なしの両方を受ける
CSRF_HEADER_NAMES = ("x-csrf-token", "x-csrftoken")
CSRF_FORM_FIELD = "csrf_token"

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{40,}$")
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS", "TRACE")


def generate_csrf_token() -> str:
    """推測できないランダムなトークンを生成する"""
    return secrets.token_urlsafe(32)


def _has_valid_format(token: str | None) -> bool:
    return bool(token) and bool(_TOKEN_RE.match(token))


def _tokens_match(a: str, b: str) -> bool:
    # 定数時間比較（タイミング攻撃の防止）。バイト列で比べ、
    # 非 ASCII 文字が来ても例外にならないようにする
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


class CSRFMiddleware:
    """トークンの発行を担当するミドルウェア（純粋な ASGI 実装）"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 既存の Cookie ヘッダーからトークンを探す
        token = None
        for key, value in scope.get("headers", []):
            if key.lower() == b"cookie":
                for part in value.decode("latin-1").split(";"):
                    name, _, val = part.strip().partition("=")
                    if name == CSRF_COOKIE_NAME:
                        token = val
                break

        if _has_valid_format(token):
            await self.app(scope, receive, send)
            return

        # トークンが無い（または不正な形式）→ 新規発行する
        token = generate_csrf_token()

        # 下流（テンプレート・検証）からもこのリクエストの Cookie として
        # 見えるよう、Cookie ヘッダーに注入しておく
        new_headers = []
        injected = False
        for key, value in scope.get("headers", []):
            if key.lower() == b"cookie" and not injected:
                value = value + f"; {CSRF_COOKIE_NAME}={token}".encode("latin-1")
                injected = True
            new_headers.append((key, value))
        if not injected:
            new_headers.append(
                (b"cookie", f"{CSRF_COOKIE_NAME}={token}".encode("latin-1"))
            )
        scope = dict(scope)
        scope["headers"] = new_headers

        async def send_with_cookie(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append(
                    "set-cookie",
                    f"{CSRF_COOKIE_NAME}={token}; HttpOnly; Path=/; SameSite=lax",
                )
            await send(message)

        await self.app(scope, receive, send_with_cookie)


async def csrf_protect(request: Request) -> None:
    """
    状態を変えるリクエストの CSRF 検証。
    main.py で FastAPI(dependencies=[...]) として全ルートに適用する。
    """
    if request.method in _SAFE_METHODS:
        return

    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not _has_valid_format(cookie_token):
        raise HTTPException(status_code=403, detail="CSRFトークンがありません")

    # HTMX は base.html のスクリプトでヘッダーに載せて送る
    for header_name in CSRF_HEADER_NAMES:
        header_token = request.headers.get(header_name)
        if header_token and _tokens_match(header_token, cookie_token):
            return

    # 通常フォームは hidden フィールドで送る
    form = await request.form()
    form_token = form.get(CSRF_FORM_FIELD)
    if form_token and _tokens_match(str(form_token), cookie_token):
        return

    raise HTTPException(
        status_code=403, detail="CSRFトークンの検証に失敗しました"
    )
```

## app/templating.py

対応: 第6章（フィルターとグローバルの追加は第7章）。正本: `app/templating.py`

```python
# app/templating.py
"""
Jinja2 テンプレートの共有モジュール。

全 Router はここで作る1つの templates オブジェクトを共有する。
カスタムフィルターもここに登録する
（Router ごとに Jinja2Templates を作ると、描画側にフィルターが届かない）。
"""
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def time_ago(dt: datetime) -> str:
    diff = int((datetime.now(timezone.utc) - dt).total_seconds())
    if diff < 60:       return "たった今"
    elif diff < 3600:   return f"{diff // 60}分前"
    elif diff < 86400:  return f"{diff // 3600}時間前"
    elif diff < 86400 * 30: return f"{diff // 86400}日前"
    else:               return f"{diff // (86400 * 30)}ヶ月前"


def urlparse_host(url: str) -> str:
    try:    return urlparse(url).hostname or url
    except: return url


templates.env.filters["time_ago"] = time_ago
templates.env.filters["urlparse_host"] = urlparse_host


# === 第7章で追加 ===

def format_karma(karma: int) -> str:
    """1000以上は k 表記にする"""
    if karma >= 1000:
        return f"{karma / 1000:.1f}k"
    return str(karma)


templates.env.filters["format_karma"] = format_karma

# 報告理由の共通データ。
# 値の正本は app/reports/services.py の VALID_REASONS。
# ここでは表示ラベルと対応づけてテンプレート全体から使えるようにする。
from app.reports.services import VALID_REASONS

REPORT_REASON_LABELS = {
    "spam": "スパム",
    "harassment": "嫌がらせ・ハラスメント",
    "hate_speech": "ヘイトスピーチ",
    "misinformation": "誤情報",
    "other": "その他",
}

templates.env.globals["report_reasons"] = [
    (value, REPORT_REASON_LABELS[value]) for value in VALID_REASONS
]
```

## alembic/env.py

対応: 第1章。正本: `alembic/env.py`

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from app.config import settings
from app.database import Base

# 全モデルをインポートしておく（マイグレーションの自動生成に必要）
import app.accounts.models      # noqa
import app.communities.models   # noqa
import app.posts.models         # noqa
import app.comments.models      # noqa
import app.reports.models       # noqa

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()

def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

## alembic/versions/XXXX_enable_uuid_extension.py

対応: 第2章。正本: `alembic/versions/XXXX_enable_uuid_extension.py`

```python
# alembic/versions/XXXX_enable_uuid_extension.py
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
```

## alembic/versions/XXXX_create_users.py

対応: 第2章。正本: `alembic/versions/XXXX_create_users.py`

```python
# alembic/versions/XXXX_create_users.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("username", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("post_karma", sa.Integer(), server_default="0", nullable=False),
        sa.Column("comment_karma", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
```

## alembic/versions/XXXX_create_subreddits.py

対応: 第2章。正本: `alembic/versions/XXXX_create_subreddits.py`

```python
# alembic/versions/XXXX_create_subreddits.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "subreddits",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("name", sa.String(21), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_subreddits_name", "subreddits", ["name"], unique=True)
    op.create_index("ix_subreddits_owner_id", "subreddits", ["owner_id"])

def downgrade() -> None:
    op.drop_index("ix_subreddits_owner_id", table_name="subreddits")
    op.drop_index("ix_subreddits_name", table_name="subreddits")
    op.drop_table("subreddits")
```

## alembic/versions/XXXX_create_subreddit_members.py

対応: 第2章。正本: `alembic/versions/XXXX_create_subreddit_members.py`

```python
# alembic/versions/XXXX_create_subreddit_members.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "subreddit_members",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("subreddit_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), server_default="member", nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subreddit_id"], ["subreddits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    # 1人1回のみ Join 可能
    op.create_index("ix_subreddit_members_unique",
                    "subreddit_members", ["user_id", "subreddit_id"], unique=True)
    op.create_index("ix_subreddit_members_user_id",
                    "subreddit_members", ["user_id"])
    op.create_index("ix_subreddit_members_subreddit_id",
                    "subreddit_members", ["subreddit_id"])

def downgrade() -> None:
    op.drop_index("ix_subreddit_members_subreddit_id", table_name="subreddit_members")
    op.drop_index("ix_subreddit_members_user_id", table_name="subreddit_members")
    op.drop_index("ix_subreddit_members_unique", table_name="subreddit_members")
    op.drop_table("subreddit_members")
```

## alembic/versions/XXXX_create_posts.py

対応: 第2章。正本: `alembic/versions/XXXX_create_posts.py`

```python
# alembic/versions/XXXX_create_posts.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),       # "text" | "link"
        sa.Column("body", sa.Text(), nullable=True),            # type=text のみ
        sa.Column("url", sa.String(2048), nullable=True),       # type=link のみ
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hot_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("subreddit_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subreddit_id"], ["subreddits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_subreddit_id", "posts", ["subreddit_id"])
    # Hot Feed 用の複合インデックス
    op.create_index("ix_posts_subreddit_hot",
                    "posts", ["subreddit_id", "hot_score"])
    # New Feed 用の複合インデックス
    op.create_index("ix_posts_subreddit_new",
                    "posts", ["subreddit_id", "inserted_at"])
    # ホーム Feed 用
    op.create_index("ix_posts_hot_score", "posts", ["hot_score"])

def downgrade() -> None:
    op.drop_index("ix_posts_hot_score", table_name="posts")
    op.drop_index("ix_posts_subreddit_new", table_name="posts")
    op.drop_index("ix_posts_subreddit_hot", table_name="posts")
    op.drop_index("ix_posts_subreddit_id", table_name="posts")
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_table("posts")
```

## alembic/versions/XXXX_create_comments.py

対応: 第2章。正本: `alembic/versions/XXXX_create_comments.py`

```python
# alembic/versions/XXXX_create_comments.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),   # 自己参照（nullable）
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])

def downgrade() -> None:
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_table("comments")
```

## alembic/versions/XXXX_create_votes.py

対応: 第2章。正本: `alembic/versions/XXXX_create_votes.py`

```python
# alembic/versions/XXXX_create_votes.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),          # +1 | -1
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),   # "post" | "comment"
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    # 1人1票の制約
    op.create_index("ix_votes_unique",
                    "votes", ["user_id", "target_type", "target_id"], unique=True)
    op.create_index("ix_votes_target",
                    "votes", ["target_type", "target_id"])

def downgrade() -> None:
    op.drop_index("ix_votes_target", table_name="votes")
    op.drop_index("ix_votes_unique", table_name="votes")
    op.drop_table("votes")
```

## alembic/versions/XXXX_create_reports.py

対応: 第2章。正本: `alembic/versions/XXXX_create_reports.py`

```python
# alembic/versions/XXXX_create_reports.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),  # "post" | "comment"
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_reports_target",
                    "reports", ["target_type", "target_id"])
    op.create_index("ix_reports_reporter_id",
                    "reports", ["reporter_id"])

def downgrade() -> None:
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_table("reports")
```

## requirements.txt

対応: 第1章。正本: `requirements.txt`

```text
# requirements.txt

# FastAPI 本体
fastapi==0.115.0
uvicorn[standard]==0.30.0

# テンプレートエンジン
jinja2==3.1.4
python-multipart==0.0.9

# DB
sqlalchemy==2.0.35
asyncpg==0.29.0
alembic==1.13.3

# バリデーション
pydantic==2.9.0
pydantic-settings==2.5.2
# EmailStr（第3章の UserCreate）を使うために必要
email-validator==2.3.0

# 認証
passlib[bcrypt]==1.7.4
# passlib 1.7.4 は bcrypt 4.1 以降と組み合わせると動作しないため版を固定する
bcrypt==4.0.1
itsdangerous==2.2.0

# 環境変数
python-dotenv==1.0.1
```

## .env

対応: 第1章（見本。値は自分の環境に合わせて書き換える）。正本: `.env`

```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/reddit_clone_dev
SECRET_KEY=your-secret-key-change-this-in-production
SESSION_COOKIE_NAME=session
DEBUG=True
```

## .gitignore

対応: 第1章。正本: `.gitignore`

```text
.env
venv/
__pycache__/
*.pyc
.DS_Store
```
