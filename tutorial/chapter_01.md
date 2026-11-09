# 第1章　プロジェクトのセットアップ

---

### この章で学ぶこと

- 作るもの: プロジェクトのディレクトリと仮想環境、依存関係の一覧（`requirements.txt`）、環境変数（`.env`）、DB 接続と設定管理、アプリの入口（`main.py` 初版）、Alembic の初期設定、共通 Depends の下ごしらえ
- 学ぶ考え方: 設定と環境変数（秘密の値をコードと分けて持つ理由）、非同期処理の入り口（`async` / `await` と非同期エンジン）、Depends による依存の渡し方

### 前提

- 第0章「必要な環境」のチェックリストが済んでいること（Python 3.10 以上、PostgreSQL に接続できること）

### 全体の中での位置

この章は、3層構造そのものを作る章ではありません。第2章以降で Data 層・Service 層・Web 層が入る「入れ物」を用意する章です。ただし、DB 接続（`app/database.py`）は Data 層の土台にあたり、`app/config.py` の設定管理は全層が使う横断部品です。

なお、この章で扱う設定ファイル（`requirements.txt`・`.env`・`.gitignore`）と `alembic/env.py` の全文は、巻末の全コード付録 1（appendix_code_01）に収録しています。

---

## 1-1　ディレクトリを作成する

まずプロジェクトのディレクトリを作成します。

```bash
mkdir reddit_clone
cd reddit_clone

# 仮想環境を作成・有効化
python -m venv venv
source venv/bin/activate    # Mac / Linux
venv\Scripts\activate       # Windows
```

以下のディレクトリ構造を作ります。

```bash
mkdir -p app/accounts
mkdir -p app/communities
mkdir -p app/posts
mkdir -p app/comments
mkdir -p app/reports
mkdir -p templates/accounts
mkdir -p templates/communities
mkdir -p templates/posts
mkdir -p templates/comments
mkdir -p templates/components
mkdir -p alembic/versions
mkdir -p static/css
```

このディレクトリの分け方は、第0章の3層構造と対応しています。`app/` の下の機能別フォルダ（accounts、communities など）の中に、モデル・サービス・ルーターが層ごとに並びます。`templates/` も画面の種類ごとに分け、`alembic/` は DB の変更履歴の置き場所です。

### 補足：`__init__.py` は作りません

上のディレクトリ（`app/` や `app/accounts/` など）には、`__init__.py` を作りません。本書では全章を通じて、どのパッケージにも `__init__.py` を置かない方針で進めます。

Python 3 には **namespace package（名前空間パッケージ）** という仕組みがあり、`__init__.py` の無いディレクトリもパッケージとして扱われます。そのため `import app.accounts.models` のような読み込みは、`__init__.py` が無くてもそのまま動きます。本書のアプリも、`__init__.py` 無しで全モジュールが読み込め、最後まで動作します。

注意点は、途中で追加しないことです。`__init__.py` のある通常のパッケージと namespace package が混ざると、読み込みの扱いがややこしくなります。もし他の資料やツールの都合で `__init__.py` を置きたくなった場合は、置く・置かないのどちらかに統一してください。

---

## 1-2　依存関係をインストールする

`requirements.txt` を作成します。

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

インストールします。

```bash
pip install -r requirements.txt
```

**読み解き**

`requirements.txt` は、このアプリが使うライブラリとその版の一覧です。版を `==` で固定しているのは、誰がいつ入れても同じ組み合わせになるようにするためです。ライブラリ同士には版の相性があり、たとえば `passlib` と `bcrypt` は、組み合わせによってはパスワードのハッシュ化が動かなくなります（`bcrypt==4.0.1` の行のコメントがその例です）。また、第3章で使う `EmailStr` には `email-validator` が別に必要で、この種の「追加で要るもの」も一覧に含めておきます。

仮想環境（venv）は、このプロジェクト専用の Python 環境をフォルダの中に作る仕組みです。有効化すると `pip install` の入れ先がその環境だけになり、他のプロジェクトとライブラリが混ざりません。

---

## 1-3　環境変数を設定する

`.env` ファイルを作成します。このファイルは Git にコミットしません。

```bash
# .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/reddit_clone_dev
SECRET_KEY=your-secret-key-change-this-in-production
SESSION_COOKIE_NAME=session
DEBUG=True
```

**重要:** `SECRET_KEY` は本番環境では必ず長くランダムな値に変更してください。

```bash
# ランダムな SECRET_KEY を生成する方法
python -c "import secrets; print(secrets.token_hex(32))"
```

`.gitignore` に `.env` を追加します。

```bash
# .gitignore
.env
venv/
__pycache__/
*.pyc
.DS_Store
```

**読み解き**

設定（接続先や秘密の鍵）をコードではなく `.env` ファイルに分けるのには、理由が2つあります。1つは、接続先は環境（開発・本番）ごとに違うので、コードを書き換えずに差し替えられるようにすること。もう1つは、`SECRET_KEY` のような秘密を、コードと一緒に配ったり公開したりする事故を防ぐことです。`.gitignore` に `.env` を入れてバージョン管理の対象から外すのは、そのための備えです。

この後 1-5 で、この `.env` を読み込む設定クラスを作ります。環境変数（OS やファイル経由で外から渡す設定値）は、プログラムの外側から与える情報の置き場所だと考えてください。

---

## 1-4　DB接続設定

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
```

**読み解き**

`create_async_engine` は非同期の DB エンジンです。通常の `create_engine` と異なり、`await` で DB 操作を行います。

非同期処理（`async` / `await`）という考え方を、ここで押さえておきます。DB への問い合わせのような「待ち時間の長い処理」では、結果を待つ間、そのスレッドが何もできずに止まってしまいます。`async def` で定義した関数の中で `await` と書くと、「この処理の結果待ちの間、ほかのリクエストの処理を進めてよい」という合図になります。この本では DB アクセスをすべて非同期に統一します（理由は第0章「なぜ Python / FastAPI なのか」を参照）。

`expire_on_commit=False` はコミット後もオブジェクトの属性にアクセスできるようにする設定です。これがないとコミット後に `user.username` などにアクセスしようとするとエラーになります。

`get_db` は `yield` を使ったジェネレータ関数です。FastAPI の `Depends` と組み合わせることで、リクエストごとに DB セッションを自動的に作成・破棄します。`yield` でセッションを「渡して」、リクエストの処理が終わると後片付け（成功時はコミット、失敗時はロールバック）をする、という前後を関数1つで包んでいるのがポイントです。使う側は「セッションが手元にある」ことだけを知っていればよく、片付けを忘れる心配がありません。

---

## 1-5　設定管理

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

**読み解き**

`pydantic_settings` の `BaseSettings` は `.env` ファイルから自動的に環境変数を読み込みます。型ヒントがあるので、`DATABASE_URL` が設定されていない場合は起動時にエラーになります。本番環境での設定ミスを早期に発見できます。「秘密の値そのものは `.env` に、読み込みと検証はこのクラスに」という分担が、1-3 の考え方の実装側です。モジュール末尾の `settings = Settings()` は、アプリ全体で1つの設定オブジェクトを使い回すためのもので、シングルトン（アプリ内で1つだけの実体）と呼ばれます。

---

## 1-6　アプリのエントリーポイント

```python
# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.database import engine, Base
from app.config import settings

# 各 Router を後でここに追加する
# from app.accounts.router import router as accounts_router
# from app.communities.router import router as communities_router

app = FastAPI(
    title="Reddit Clone",
    debug=settings.DEBUG
)

# 静的ファイル（CSS・JS）の配信
app.mount("/static", StaticFiles(directory="static"), name="static")

# ヘルスチェック
@app.get("/health")
async def health():
    return {"status": "ok"}
```

> これは途中経過です。この `main.py` は第1章時点の最小形です。Router の登録は第5章で行い、CSRF の組み込みまで含めた完成形は第6章 6-16 に全文があります（全コード付録 1 にも収録しています）。

**読み解き**

`main.py` はアプリの入口です。今は `/health`（サーバーが生きているかを確認するためだけの応答）しかありませんが、この後ここに Router（画面ごとの受け口をまとめたもの）を登録していきます。`app.mount("/static", ...)` は CSS や画像などの静的ファイルの置き場所の宣言です（この本では CSS は CDN を使うため、実際にファイルは置きません）。

---

## 1-7　Alembic の初期設定

```bash
alembic init alembic
```

このコマンドは以下のファイルを生成します。

| 生成物 | このチュートリアルでの扱い |
|---|---|
| `alembic.ini` | **生成されたまま使う**。ただし接続先 URL は `env.py` が `settings.DATABASE_URL` で上書きするため、`alembic.ini` 側の `sqlalchemy.url` は実際には使われない |
| `alembic/env.py` | **下記の内容で丸ごと差し替える**（生成直後の env.py は同期エンジン前提のため） |
| `alembic/versions/` | 空のディレクトリ。第2章でマイグレーションファイルをここに作る |
| `alembic/script.py.mako` | **生成されたまま使う**（新しいマイグレーションを生成するときの雛形） |

なお、第2章で作るマイグレーションファイルには、Alembic が実行順序を特定するための `revision` / `down_revision` の宣言が必須です。本書では第2章の順序どおりに `0001` → `0008` の連鎖にしています（宣言が無いと `alembic upgrade head` が「revision を特定できない」というエラーで失敗します）。

`alembic/env.py` を編集して、SQLAlchemy の非同期エンジンに対応させます。

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

**読み解き**

`env.py` は、マイグレーションを実行するときの「実行係」です。アプリ本体は非同期エンジンで DB に接続しますが、Alembic は同期的な実行を前提に作られているため、`conn.run_sync(...)` を使って「同期の顔」をさせ、非同期接続の上でマイグレーションを動かしています。`target_metadata = Base.metadata` は、自動生成（autogenerate）が「あるべきテーブルの姿」を知るための指定で、ファイル冒頭で全モデルを import しているのはそのためです。本書では第2章のマイグレーションを手で書くため自動生成は使いませんが、この指定はそのまま残します。

---

## 1-8　動作確認（サーバーの起動）

サーバーを起動します。

```bash
uvicorn main:app --reload
```

ブラウザで `http://localhost:8000/health` を開いてください。

```json
{"status": "ok"}
```

と表示されれば成功です。

FastAPI は自動的に API ドキュメントを生成します。

```
http://localhost:8000/docs   ← Swagger UI
http://localhost:8000/redoc  ← ReDoc
```

---

## 1-9　共通 Depends の準備

認証で使う共通の Depends を先に定義しておきます。

```python
# app/dependencies.py
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Cookie からセッションを読み取り、現在のユーザーを返す。
    未ログインの場合は None を返す。
    """
    from itsdangerous import URLSafeTimedSerializer, BadSignature
    from app.accounts.services import get_user_by_id

    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_token:
        return None

    try:
        s = URLSafeTimedSerializer(settings.SECRET_KEY)
        user_id = s.loads(session_token, max_age=60 * 60 * 24 * 7)  # 7日間有効
    except BadSignature:
        return None

    return await get_user_by_id(db, user_id)


async def require_auth(
    current_user = Depends(get_current_user)
):
    """
    ログインが必要なエンドポイントで使う。
    未ログインの場合は 401 を返す。
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"}
        )
    return current_user
```

**読み解き**

`get_current_user` は Cookie からセッショントークンを取り出し、`itsdangerous` で検証します。Elixir版の `fetch_current_user` Plug に相当します。

`require_auth` は `get_current_user` に依存しています。FastAPI の `Depends` はこのような**依存の連鎖**を自動的に解決します。

```
require_auth
  └─ Depends(get_current_user)
       └─ Depends(get_db)
```

エンドポイントで `Depends(require_auth)` を指定するだけで、DB接続・セッション確認・ユーザー取得が全て自動的に行われます。

なお、この 1-9 の版は **第5章 5-3 で全面置き換え** します（トークンの検証を `app/auth.py` に任せ、ユーザーID の型変換も入る形になります。これは途中経過です）。ここでは「Depends の連鎖」という考え方をつかむための下ごしらえとして置いています。置き換えの理由は 5-3 で説明します。

---

## 動作確認（この章の仕上げ）

1-8 の起動確認に加えて、この章の終わりに次を確かめてください。

- [ ] `pip install -r requirements.txt` がエラーなく終わる（`bcrypt` が 4.0.1 で入っていること）
- [ ] `.env` の `DATABASE_URL` が、自分の PostgreSQL の接続情報と合っている
- [ ] `uvicorn main:app --reload` で起動し、`http://localhost:8000/health` が `{"status": "ok"}` を返す
- [ ] `http://localhost:8000/docs` で API ドキュメントが開く
- [ ] `alembic/` の中に `env.py` と、空の `versions/` がある

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| `pip install` で失敗する、または後の章で登録時に「password cannot be longer than 72 bytes」というエラーが出る | `passlib` と `bcrypt` の版の組み合わせが合っていない | `requirements.txt` のとおり `bcrypt==4.0.1` に固定されているか確認し、仮想環境に入れ直す |
| 起動時に `DATABASE_URL` が無いという検証エラーで止まる | `.env` が無い、または項目が欠けている | プロジェクト直下に `.env` があるか、1-3 の項目がそろっているか確認する |
| `/health` に接続できない | サーバーが起動していない、またはポート 8000 が他で使われている | 起動コマンドの出力（エラーログ）を確認する。ポートが使用中なら、先に起動したサーバーを止める |
| `alembic` コマンドが見つからない | 仮想環境が有効化されていない | `source venv/bin/activate`（Windows は `venv\Scripts\activate`）をしてから試す |

---

## 確認問題

1. `requirements.txt` で版を `==` で固定するのはなぜですか。特に `bcrypt==4.0.1` のように個別に版を指定している行があるのは、どういう理由からですか。
2. `SECRET_KEY` をコードに直接書かず `.env` に置く理由を、2つ挙げてください。
3. `get_db` が `return` ではなく `yield` を使っているのはなぜですか。使う側（Router）から見て、何が楽になりますか。
4. Depends の連鎖（`require_auth` → `get_current_user` → `get_db`）について、エンドポイント側が意識しなくてよいのは何ですか。

---

## まとめと次章へのつながり

この章では以下を完了しました。

```
✅ プロジェクトディレクトリの作成
✅ 仮想環境のセットアップ
✅ 依存関係のインストール
✅ 環境変数の設定
✅ 非同期 DB 接続の設定
✅ Alembic の初期設定
✅ サーバーの起動と動作確認
✅ 共通 Depends の準備
```

次の章では、アプリの土台となるデータベースのテーブル設計を行います。Elixir版と同じ7つのテーブルを Alembic で実装します。そのときに使うのが、この章で用意した DB 接続（`app/database.py`）と、Alembic の実行係（`alembic/env.py`）です。

---

## 確認問題の答え

1. 誰がいつ入れても、動作を確認した組み合わせとまったく同じになるようにするためです。`bcrypt` は、`passlib` 1.7.4 が 4.1 以降の版と組み合わさるとパスワードのハッシュ化が失敗するという相性の問題があり、確認済みの 4.0.1 に固定しています。
2. 1つは、接続先や鍵は環境（開発・本番）ごとに違うため、コードを書き換えずに差し替えられるようにすることです。もう1つは、秘密の値をコードと一緒に配布・公開してしまう事故を防ぐことです（`.gitignore` でバージョン管理の対象からも外します）。
3. セッションを「渡す前」と「使い終わった後」の両方に処理を挟むためです。`yield` の後ろにコミットやロールバック（後片付け）を書いておけるので、使う側はセッションを受け取って使うだけでよく、片付けを書く必要も、忘れる心配もありません。
4. DB セッションの用意と片付け、Cookie からのユーザー特定、その実行順序です。エンドポイントは `Depends(require_auth)` と宣言するだけで、前提の処理が連鎖的にすべて実行されます。
