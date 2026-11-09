# 第5章　認証（前編）

---

### この章で学ぶこと

- 作るもの: セッションのヘルパー（`app/auth.py`）、共通 Depends（`app/dependencies.py`）、認証 Router（登録・ログイン・ログアウト・プロフィール）、テンプレート（ベース・登録・ログイン・404）、CSRF 対策（`app/csrf.py`）
- 学ぶ考え方: 署名付き Cookie（暗号化ではなく改ざん検出）、Depends による依存の注入、フォームの受け取りと PRG パターン、CSRF とダブルサブミットクッキー方式

### 前提

- 第4章までが終わっていること（Service 層がそろっていること）。この章は、その Service を呼ぶ「入口」を作ります
- プロフィールのテンプレート（`templates/accounts/profile.html`）は第7章 7-6 で作成します。この章では Router までを完成させます

### 全体の中での位置

この章は Web 層の入口を作る章ですが、認証は全層にまたがる横断部品でもあります。`app/auth.py` と `app/dependencies.py` は、第6章以降のすべての Router が使い続けます。「ログインしているのは誰か」を各画面が同じ方法で知るための土台を、ここで固めます。

なお、`app/auth.py`・`app/dependencies.py`・`app/csrf.py` の全文は全コード付録 1（appendix_code_01）に、認証 Router の全文は全コード付録 3（appendix_code_03）に、テンプレートの全文は全コード付録 4（appendix_code_04）に収録しています。

---

## 5-1　Cookie セッションの仕組み

FastAPI には Django のような組み込み認証がありません。`itsdangerous` を使って自前で実装します。

```
ログイン時
  ① フォームで email + password を送信
  ② サーバーでパスワードを照合
  ③ user_id を itsdangerous で署名してトークンを生成
  ④ トークンを Cookie に保存してレスポンスを返す

その後のリクエストごとに
  ⑤ ブラウザが Cookie を自動的に送ってくる
  ⑥ Cookie からトークンを取り出す
  ⑦ itsdangerous で署名を検証・user_id を取り出す
  ⑧ DB からユーザーを取得して request.state に入れる
```

Elixir版との比較です。

```
Elixir版                    FastAPI版
────────────────────────────────────────────────
Phoenix.Token.sign()    →   serializer.dumps()
Phoenix.Token.verify()  →   serializer.loads()
on_mount :fetch_user    →   Depends(get_current_user)
on_mount :require_auth  →   Depends(require_auth)
plug :fetch_current_user→   Depends(get_current_user)
```

---

## 5-2　セッションのヘルパー関数

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

**読み解き**

まず押さえておきたいのは、このトークンは「署名付き」ですが「暗号化」ではない、という点です。トークンの中身（ここでは user_id）は、形式を解読すれば誰でも読めます。署名が守っているのは中身の秘密ではなく、「サーバーが発行したものから書き換えられていないこと」です。中身を1文字でも変えると署名が合わなくなり、検証で弾かれます。ちょうど、封筒の中身は見えても、封蝋（ふうろう）が割れていれば開けられたと分かる、という関係です。

ですから、Cookie に入れてよいのは「読まれてもよいが、書き換えられると困る」情報だけです。user_id はその条件に合いますが、パスワードや個人情報を入れてはいけません。秘密にしなければならないのは中身ではなく、署名に使う `SECRET_KEY` の方です。また `loads` の `max_age` により、署名が正しくても発行から7日を過ぎたトークンは弾かれます（発行時刻も署名の対象に含まれているため、時刻のごまかしもできません）。

`salt="session"` は署名の用途を分けるための文字列です。発行側（`create_session_token`）と検証側（`verify_session_token`）で**同じ salt を指定しなければ検証は失敗します**。この点は 5-3 で重要になります。

`httponly=True` は JavaScript から Cookie にアクセスできなくします。XSS 攻撃でトークンが盗まれることを防ぎます。

`samesite="lax"` は別サイトからのフォーム送信で Cookie を送らない設定です。CSRF 攻撃を軽減します。

`secure=not settings.DEBUG` は本番環境（DEBUG=False）では HTTPS 接続のみで Cookie を送ります。

---

## 5-3　Depends の実装

> **重要**: ここで作る `app/dependencies.py` は、第1章 1-9 で作った初版を**全面置き換え**します。追記ではなく、ファイルごと差し替えてください。
>
> 理由は salt の扱いです。1-9 版はトークンの検証を自前で書いており、salt を指定していませんでした。一方 5-2 の `create_session_token` は `salt="session"` で署名します。1-9 版のままでは 5-2 が発行したトークンを検証できないため、検証は 5-2 の `verify_session_token`（同じ salt を使う）に任せるこの版へ置き換えます。

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

**読み解き**

`Depends` は「依存の注入」という仕組みです。エンドポイントの引数に `db: AsyncSession = Depends(get_db)` のように書いておくと、FastAPI がリクエストのたびに `get_db` を先に実行し、その結果を引数へ渡してくれます。エンドポイント側は「セッションが要る」と宣言するだけで、自分で用意しません。第1章の `get_db` も、この仕組みで渡される部品の1つです。

部品は入れ子にもできます。`require_auth` は `get_current_user` に依存し、`get_current_user` は `get_db` に依存しています。FastAPI はこの依存の連鎖をたどって、必要なものを順に用意します。おかげで、「ログイン必須」の指定は `Depends(require_auth)` と書くだけで済み、エンドポイント本体には認証の手順を書かずに済みます。

3つの関数の役割の違いも見ておきます。`get_current_user` は「分からなければ `None`」と答えるだけの係です。`require_auth` と `redirect_if_authenticated` は、その答えを見て、続行できない場合に `HTTPException`（303 リダイレクト）を**投げて**処理を止める係です。「投げる」ことで、呼び出し側のエンドポイントは例外処理を書かずに済みます。

---

## 5-4　認証 Router の実装

> **この節のコードについて（途中経過の部分）**: この Router は、この時点では冒頭の3行で `Jinja2Templates` を自前で作っています（`from fastapi.templating import Jinja2Templates` と `templates = Jinja2Templates(directory="templates")`）。第6章 6-15 で、テンプレート基盤とカスタムフィルターを `app/templating.py` に集約し、この3行を `from app.templating import templates` に置き換えます。その置き換え後の姿が完成形です（完成形の全文は全コード付録 3 にあります）。それ以外の部分は、この節の提示のままで変わりません。

```python
# app/accounts/router.py
from fastapi import APIRouter, Depends, Query, Request, Response, Form
from typing import Literal
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, redirect_if_authenticated
from app.accounts import services
from app.accounts.schemas import UserCreate
from app.auth import set_session_cookie, clear_session_cookie

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ----------------------------------------------------------------
# 登録
# ----------------------------------------------------------------

@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    _=Depends(redirect_if_authenticated)
):
    """登録ページを表示する"""
    return templates.TemplateResponse(
        "accounts/register.html",
        {"request": request, "errors": {}}
    )


@router.post("/register")
async def register(
    request: Request,
    response: Response,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """ユーザーを登録する"""
    errors = {}

    # Pydantic でバリデーション
    try:
        data = UserCreate(username=username, email=email, password=password)
    except Exception as e:
        for error in e.errors():
            field = error["loc"][0]
            errors[field] = error["msg"]
        return templates.TemplateResponse(
            "accounts/register.html",
            {"request": request, "errors": errors,
             "username": username, "email": email},
            status_code=422
        )

    # DB に保存
    try:
        user = await services.create_user(db, data)
    except ValueError as e:
        errors["general"] = str(e)
        return templates.TemplateResponse(
            "accounts/register.html",
            {"request": request, "errors": errors,
             "username": username, "email": email},
            status_code=422
        )

    # 登録成功 → 自動ログイン
    redirect = RedirectResponse(url="/", status_code=303)
    set_session_cookie(redirect, str(user.id))
    return redirect


# ----------------------------------------------------------------
# ログイン
# ----------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    _=Depends(redirect_if_authenticated)
):
    """ログインページを表示する"""
    return templates.TemplateResponse(
        "accounts/login.html",
        {"request": request, "error": None}
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """ログインする"""
    user = await services.authenticate_user(db, email, password)

    if user is None:
        # 失敗理由は曖昧にする（セキュリティ上の理由）
        return templates.TemplateResponse(
            "accounts/login.html",
            {
                "request": request,
                "error": "メールアドレスまたはパスワードが違います",
                "email": email   # メールは残す・パスワードは残さない
            },
            status_code=401
        )

    # ログイン成功 → Cookie をセット
    redirect = RedirectResponse(url="/", status_code=303)
    set_session_cookie(redirect, str(user.id))
    return redirect


# ----------------------------------------------------------------
# ログアウト
# ----------------------------------------------------------------

@router.post("/logout")
async def logout():
    """ログアウトする（Cookie を削除する）"""
    redirect = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(redirect)
    return redirect


# ----------------------------------------------------------------
# プロフィール
# ----------------------------------------------------------------

@router.get("/u/{username}", response_class=HTMLResponse)
async def profile(
    request: Request,
    username: str,
    sort: Literal["hot", "new"] = Query("new"),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.posts.services import list_user_posts

    profile_user = await services.get_user_by_username(db, username)
    if profile_user is None:
        return templates.TemplateResponse(
            "404.html", {"request": request}, status_code=404
        )

    posts, has_more = await list_user_posts(
        db, profile_user.id, sort, page
    )

    return templates.TemplateResponse(
        "accounts/profile.html",
        {
            "request": request,
            "current_user": current_user,
            "profile_user": profile_user,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": has_more
        }
    )
```

**読み解き**

`Form(...)` は HTML フォームの入力値を受け取ります。`...` は必須を意味します。

```python
username: str = Form(...)   # 必須
page: int = Form(1)         # デフォルト値あり（任意）
```

ログイン失敗時のエラーメッセージは「メールアドレスまたはパスワードが違います」のみです。「メールが存在しません」と「パスワードが違います」を分けて伝えると、攻撃者がどのメールが登録済みかを判断できてしまいます。

プロフィールの投稿一覧では `sort` と `page` を受け取ります。従来の表示順を保つため並び方の既定は `new` とし、許可する値は `hot` と `new` だけです。`page` は `Query(1, ge=1)` で 1 以上だけを許可します。不正な並び方や `page=0` のような値は Service に届く前に 422 になります。Service からは表示する投稿と `has_more` の組が返ります。

`status_code=303` は POST 後のリダイレクトで使います。`303 See Other` はブラウザに「次は GET で取得してください」と伝えます。これにより、ページをリロードしたときにフォームが再送信されることを防ぎます（PRG パターン）。

なお、この Router が描画する `templates/accounts/profile.html` は、まだ作っていません。プロフィールのテンプレートは第7章 7-6 で作成するため、この時点では `/u/{username}` の動作確認はできません（Router 自体はここで完成です）。

### 404 テンプレートの作成

上のプロフィール Router は、存在しないユーザーに対して `404.html` を返します。このテンプレートが無いと、404 ではなくエラー（500）になってしまうため、ここで作成しておきます。

```html
<!-- templates/404.html -->
{% extends "base.html" %}

{% block title %}ページが見つかりません · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-16 text-center">
  <p class="text-6xl mb-4">🔍</p>
  <h1 class="text-2xl font-bold text-gray-800 mb-2">ページが見つかりません</h1>
  <p class="text-sm text-gray-500 mb-6">
    お探しのページは存在しないか、削除された可能性があります。
  </p>
  <a href="/"
    class="inline-block px-4 py-2 bg-blue-500 text-white text-sm rounded hover:bg-blue-600">
    ホームへ戻る
  </a>
</div>
{% endblock %}
```

`base.html` は後編（5-5）で作成します。ここではファイルを用意するところまでで構いません。

---

後編ではテンプレート（登録・ログイン画面）を実装します。
