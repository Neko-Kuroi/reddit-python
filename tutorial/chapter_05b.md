# 第5章　認証（後編）

---

## 5-5　ベーステンプレート

全画面で共通のナビゲーションバーを持つベーステンプレートを作ります。

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{% block title %}reddit_clone{% endblock %}</title>

  <!-- Tailwind CSS（CDN） -->
  <script src="https://cdn.tailwindcss.com"></script>

  <!-- HTMX -->
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>

  <!-- CSRF トークン（HTMX のリクエストに自動付与） -->
  <!-- 値はミドルウェアが発行した Cookie と同じもの（app/csrf.py） -->
  <meta name="csrf-token" content="{{ request.cookies.get('csrf_token', '') }}" />
  <script>
    document.addEventListener("htmx:configRequest", (e) => {
      e.detail.headers["X-CSRFToken"] = document
        .querySelector('meta[name="csrf-token"]').content;
    });
  </script>
</head>

<body class="bg-gray-100 min-h-screen">

  <!-- ナビゲーションバー -->
  <nav class="bg-white border-b border-gray-200 sticky top-0 z-30">
    <div class="max-w-5xl mx-auto px-4 h-12 flex items-center gap-4">

      <!-- ロゴ -->
      <a href="/" class="flex items-center gap-1 shrink-0">
        <span class="text-orange-500 text-xl font-black">🔴</span>
        <span class="font-bold text-gray-800 hidden sm:block">reddit_clone</span>
      </a>

      <!-- 検索フォーム -->
      <form action="/search" method="get" class="flex-1 max-w-xl">
        <div class="relative">
          <input
            type="text"
            name="q"
            value="{{ query | default('') }}"
            placeholder="検索..."
            class="w-full border border-gray-300 rounded-full px-4 py-1.5 text-sm
                   bg-gray-50 focus:outline-none focus:border-blue-400"
          />
          <button type="submit"
            class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
            🔍
          </button>
        </div>
      </form>

      <!-- 右側: 認証ボタン -->
      <div class="flex items-center gap-2 shrink-0">
        {% if current_user %}
          <a href="/u/{{ current_user.username }}"
            class="text-sm text-gray-700 hover:text-blue-500 font-medium hidden sm:block">
            u/{{ current_user.username }}
          </a>
          <a href="/subreddits/new"
            class="text-sm text-gray-500 hover:text-gray-700 px-2 hidden sm:block">
            ＋ 作成
          </a>
          <form action="/logout" method="post" class="inline">
            <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />
            <button type="submit"
              class="text-sm border border-gray-300 rounded-full px-3 py-1 hover:bg-gray-50">
              ログアウト
            </button>
          </form>
        {% else %}
          <a href="/login"
            class="text-sm border border-blue-500 text-blue-500 rounded-full px-3 py-1 hover:bg-blue-50">
            ログイン
          </a>
          <a href="/register"
            class="text-sm bg-blue-500 text-white rounded-full px-3 py-1 hover:bg-blue-600">
            登録
          </a>
        {% endif %}
      </div>

    </div>
  </nav>

  <!-- メインコンテンツ -->
  <main>
    {% block content %}{% endblock %}
  </main>

  <!-- 共通スクリプト -->
  <script>
    // コメントの返信フォームを開閉する（comment_tree.html から使う）
    function toggleReplyForm(commentId) {
      document.getElementById("reply-form-" + commentId).classList.toggle("hidden");
    }
  </script>

</body>
</html>
```

**読み解き**

Jinja2 のテンプレート継承を使います。

```html
{% block title %}...{% endblock %}   ← 子テンプレートで上書きできる
{% block content %}...{% endblock %} ← 各ページのコンテンツが入る
```

`{{ current_user }}` はナビバーで使います。各 Router のエンドポイントで `current_user` をテンプレートに渡す必要があります。

ログアウトは `<form method="post">` で実装します。`<a>` タグは GET リクエストしか送れないため、ログアウトのような副作用のある操作は POST で行います。そのため、ログアウトフォームにも CSRF トークンの hidden フィールドを入れます（検証の仕組みは 5-9 で実装します）。

CSRF トークンは、ミドルウェア（5-9 の `app/csrf.py`）が発行して Cookie に入れた値を、`request.cookies` 経由で meta タグに描画します。HTMX のリクエストには、ここに入れた JavaScript がその値を `X-CSRFToken` ヘッダーとして自動付与します。通常のフォームは hidden フィールドで同じトークンを送ります。

`<body>` の末尾には共通スクリプト置き場を用意し、コメントの返信フォームを開閉する `toggleReplyForm` を定義します（第6章の CommentTree コンポーネントから使います）。

---

## 5-6　登録ページのテンプレート

```html
<!-- templates/accounts/register.html -->
{% extends "base.html" %}

{% block title %}ユーザー登録 · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-md mx-auto mt-16 p-6">
  <h1 class="text-2xl font-bold mb-6">アカウントを作成</h1>

  {% if errors.general %}
    <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
      {{ errors.general }}
    </div>
  {% endif %}

  <form action="/register" method="post" class="space-y-4">
    <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />

    <!-- ユーザー名 -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        ユーザー名
      </label>
      <input
        type="text"
        name="username"
        value="{{ username | default('') }}"
        placeholder="例: alice"
        class="w-full border {% if errors.username %}border-red-400{% else %}border-gray-300{% endif %}
               rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
      />
      {% if errors.username %}
        <p class="text-red-500 text-xs mt-1">{{ errors.username }}</p>
      {% endif %}
    </div>

    <!-- メールアドレス -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        メールアドレス
      </label>
      <input
        type="email"
        name="email"
        value="{{ email | default('') }}"
        class="w-full border {% if errors.email %}border-red-400{% else %}border-gray-300{% endif %}
               rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
      />
      {% if errors.email %}
        <p class="text-red-500 text-xs mt-1">{{ errors.email }}</p>
      {% endif %}
    </div>

    <!-- パスワード -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        パスワード（8文字以上）
      </label>
      <input
        type="password"
        name="password"
        class="w-full border {% if errors.password %}border-red-400{% else %}border-gray-300{% endif %}
               rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
      />
      {% if errors.password %}
        <p class="text-red-500 text-xs mt-1">{{ errors.password }}</p>
      {% endif %}
    </div>

    <button type="submit"
      class="w-full bg-blue-500 text-white rounded py-2 text-sm font-medium hover:bg-blue-600">
      登録する
    </button>

  </form>

  <p class="mt-4 text-center text-sm text-gray-500">
    すでにアカウントをお持ちですか？
    <a href="/login" class="text-blue-500 hover:underline">ログイン</a>
  </p>
</div>
{% endblock %}
```

---

## 5-7　ログインページのテンプレート

```html
<!-- templates/accounts/login.html -->
{% extends "base.html" %}

{% block title %}ログイン · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-md mx-auto mt-16 p-6">
  <h1 class="text-2xl font-bold mb-6">ログイン</h1>

  {% if error %}
    <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4 text-sm">
      {{ error }}
    </div>
  {% endif %}

  <form action="/login" method="post" class="space-y-4">
    <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />

    <!-- メールアドレス -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        メールアドレス
      </label>
      <input
        type="email"
        name="email"
        value="{{ email | default('') }}"
        class="w-full border border-gray-300 rounded px-3 py-2 text-sm
               focus:outline-none focus:border-blue-400"
      />
    </div>

    <!-- パスワード -->
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        パスワード
      </label>
      <input
        type="password"
        name="password"
        class="w-full border border-gray-300 rounded px-3 py-2 text-sm
               focus:outline-none focus:border-blue-400"
      />
    </div>

    <button type="submit"
      class="w-full bg-blue-500 text-white rounded py-2 text-sm font-medium hover:bg-blue-600">
      ログイン
    </button>

  </form>

  <p class="mt-4 text-center text-sm text-gray-500">
    アカウントをお持ちでないですか？
    <a href="/register" class="text-blue-500 hover:underline">新規登録</a>
  </p>
</div>
{% endblock %}
```

---

## 5-8　main.py に Router を登録する

```python
# main.py（更新版）
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.accounts.router import router as accounts_router

app = FastAPI(title="Reddit Clone", debug=settings.DEBUG)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Router を登録する
app.include_router(accounts_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

**読み解き**

Router は「部品」で、`main.py` は「組み立て場所」です。`app.include_router(...)` で取り付けて初めて、その Router の URL が有効になります。この時点では認証 Router だけを取り付けます。第6章で残りの Router を足し、5-9 の CSRF の登録も加わって、6-16 で完成版になります。

---

## 5-9　CSRF 対策の実装

5-5 のベーステンプレートには CSRF トークンを送る仕組み（meta タグと HTMX 用スクリプト、フォームの hidden フィールド）を入れてありました。ここでは受け取る側、つまり**発行と検証**を実装します。

方式は**ダブルサブミットクッキー**です。

1. サーバーがランダムなトークンを生成し、Cookie（`csrf_token`）に入れてブラウザに渡す
2. ブラウザは状態を変えるリクエスト（POST 等）のたびに、同じトークンを「フォームの hidden フィールド」または「`X-CSRF-Token` ヘッダー（HTMX）」でも送る
3. サーバーは Cookie の値と一緒に送られてきた値を比べ、一致しなければ 403 で拒否する

悪意のあるサイトは、被害者のブラウザに Cookie を自動で送らせることはできても、**Cookie の中身を読むことはできない**（同一オリジン制限）ため、正しいトークンを一緒に送ることができません。これが防御の原理です。セッション Cookie の `samesite="lax"` はこれを補助する設定で、対策の本体はこちらの検証です。

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

**読み解き**

発行と検証で置き場所を分けているのがポイントです。

- **発行はミドルウェア**。GET のページ表示も含め、トークンの無いリクエストすべてに Cookie を配る必要があるためです。発行時に Cookie ヘッダーへも同じ値を注入するのは、そのリクエストで描画されるページ（meta タグと hidden フィールド）に、発行したてのトークンを載せるためです。
- **検証は依存性（Depends）**。フォームの読み取りは FastAPI のリクエスト処理の中で行うのが安全なためです（ミドルウェアでリクエストボディを先に読むと、後段のフォーム解析と競合しやすくなります）。

`main.py` への登録は 5-8 の版に以下を加えます（第6章の完成版にも同じ形で入ります）。

```python
# main.py（5-9 で追加）
from fastapi import Depends, FastAPI
from app.csrf import CSRFMiddleware, csrf_protect

app = FastAPI(
    title="Reddit Clone",
    debug=settings.DEBUG,
    dependencies=[Depends(csrf_protect)],   # 全ルートで検証する
)

app.add_middleware(CSRFMiddleware)           # トークンを発行する
```

これで、ログイン・登録・ログアウトをはじめ、このアプリのすべての POST が検証対象になります。トークンを送らない POST は 403 になるため、第6章以降でフォームを作るときは、通常フォームには hidden フィールド、HTMX には base.html のヘッダー付与スクリプト、という約束を守ってください。

---

## 動作確認（この章の仕上げ）

前提: 第2章のマイグレーションが適用済みで、PostgreSQL に接続できること。サーバーを起動して、ブラウザで確かめます。なお、ホーム（`/`）の画面そのものは第6章で Router が入ってから表示されます。この章では「認証まわり」だけを確認します。

- [ ] `GET /health` が `{"status": "ok"}` を返す
- [ ] `/register` で登録するとリダイレクトされ、ブラウザにセッション Cookie が保存される（開発者ツールで `session` という名前の Cookie を確認する）
- [ ] 登録済みのメールアドレスでもう一度登録すると、422 でエラーが画面に出る（500 にはならない）
- [ ] `/login` で、間違ったパスワードでは 401 になり、「メールアドレスまたはパスワードが違います」とだけ表示される。正しい資格情報ではログインできる
- [ ] ログアウトするとセッション Cookie が消え、`/login` へ戻る
- [ ] CSRF の確認: Cookie とトークンを送らずに `curl -X POST http://localhost:8000/login -d "email=a@b.c&password=x"` を実行すると 403 になる。ブラウザからの通常のログイン（トークン付き）は従来どおり通る
- [ ] （第7章の後に）`/u/{自分のユーザー名}` でプロフィールが表示され、`/u/nobody` のような存在しないユーザーは 404 ページになる

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| 登録できるのに、その直後から未ログイン扱いになる（トークンの検証が常に失敗する） | 発行側と検証側で salt が違う。第1章 1-9 版の `dependencies.py` が残っていると、発行側の `salt="session"` と食い違う | 5-3 の版で `app/dependencies.py` を全面置き換える（追記では直らない） |
| ログイン直後のリクエストで、ユーザー取得まわりの DB エラーになる | トークンから取り出した user_id は文字列で、DB 側の UUID 型と合わないことがある | 5-3 の `get_current_user` のように、`uuid.UUID(...)` に変換してから照合する |
| ページは表示されるのに、フォームを送ると全て 403 になる | CSRF トークンが送られていない。フォームの hidden フィールドの欠落、または base.html の meta タグにトークンが描画されていない | フォームに `csrf_token` の hidden フィールドがあるか、meta タグの値が空でないかを確認する（5-5・5-9） |
| 存在しないユーザーのプロフィールを開くと 500 になる | `templates/404.html` が無いため、404 を返そうとして描画に失敗している | 5-4 で `404.html` を作成する |
| 登録のときに `ValueError: password cannot be longer than 72 bytes` のようなエラーが出る | passlib と bcrypt の版の組み合わせが合っていない（現在の bcrypt では passlib が正しく動かない） | 第1章の `requirements.txt` のとおり、bcrypt を固定した版にする |
| 設定を変えたのにセッション Cookie が保存されない | `secure` 属性の効いた Cookie は、HTTPS でないと送られない。`DEBUG=False` のまま HTTP で開いている | 開発中は `.env` の `DEBUG` を確認する。本番では HTTPS で運用する |

---

## 確認問題

1. セッショントークンは「署名付き」ですが「暗号化」ではありません。その違いを踏まえて、Cookie に入れてよい情報と、いけない情報の区別を説明してください。
2. `get_current_user` と `require_auth` は何が違いますか。未ログインのとき、それぞれ何を返し（または何を起こし）ますか。
3. 攻撃者のサイトは、被害者のブラウザに Cookie を自動で送らせることができます。それでもダブルサブミットクッキー方式で CSRF を防げるのはなぜですか。
4. 5-9 では、トークンの「発行」をミドルウェア、「検証」を依存性（Depends）に分けています。なぜですか。
5. ログイン失敗のときに「メールアドレスが存在しません」と「パスワードが違います」を分けて表示しないのはなぜですか。

---

## まとめと次章へのつながり

この章では以下を完了しました。

```
✅ itsdangerous でトークンを署名・検証する方法を学んだ
✅ httponly / samesite / secure Cookie の設定を理解した
✅ get_current_user / require_auth Depends を実装した
✅ 登録・ログイン・ログアウト Router を実装した
✅ Jinja2 テンプレート継承を使ったベーステンプレートを作った
✅ PRG パターン（303 See Other）を実装した
✅ CSRF 対策（ダブルサブミットクッキー方式）を実装した
```

**セキュリティの重要なポイント**

```
httponly=True     → XSS でトークンが盗まれない
CSRF トークン検証  → ダブルサブミットクッキー方式で状態変更リクエストを検証し、不一致は 403（5-9）
samesite="lax"   → CSRF 対策の補助（別サイトからの送信で Cookie を送りにくくする）
secure=True       → 本番では HTTPS のみで Cookie を送る
ログイン失敗の理由を分けない → 攻撃者に情報を与えない
dummy_verify()    → タイミング攻撃を防ぐ
PRG パターン      → リロードでフォームが再送信されない
```

次の章では Communities・Posts・Comments の Router と Jinja2 テンプレートを実装します。この章で作った `get_current_user` / `require_auth` は、第6章のすべての Router が「ログインしているのは誰か」を知るために使い続けます。CSRF の約束（通常フォームは hidden フィールド、HTMX はヘッダー）も、第6章以降のすべてのフォームの前提になります。

---

## 確認問題の答え

1. 署名は「中身が書き換えられていないこと」を保証するもので、中身自体は読めます。暗号化は中身を読めなくするものです。ですから Cookie に入れてよいのは、user_id のように「読まれてもよいが、書き換えられると困る」情報だけで、パスワードのような秘密の情報を入れてはいけません。秘密にすべきなのは中身ではなく、署名に使う `SECRET_KEY` です。
2. `get_current_user` は「今のユーザーは誰か」を答える係で、未ログインなら `None` を返します。`require_auth` はその答えを見て門番をする係で、未ログインなら 303 の `HTTPException` を投げて処理を止め、ログインページへ送ります。
3. 攻撃者は Cookie を「送らせる」ことはできても、「読む」ことはできないからです（同一オリジン制限）。ダブルサブミット方式は Cookie と同じ値をもう1経路（フォームやヘッダー）で送らせるため、正規の画面を持たない攻撃者は、正しい値を一緒に送ることができません。
4. 発行は、ページ表示（GET）を含むすべてのリクエストに Cookie を配る必要があるため、全体に効くミドルウェアが向いています。検証はフォームの内容を読む必要があり、それは FastAPI のリクエスト処理の中で行うのが安全なため、依存性にしています（ミドルウェアで本文を先読みすると、後段のフォーム解析と競合しやすくなります）。
5. 分けて表示すると、攻撃者が「どのメールアドレスが登録済みか」を確かめられてしまうからです。理由を曖昧にすることで、登録の有無という情報自体を渡さないようにしています（第4章の `authenticate_user` が失敗理由を曖昧にするのと同じ考え方です）。
