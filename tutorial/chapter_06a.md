# 第6章　画面実装（前編）— Communities

---

### この章で学ぶこと

- 作るもの: 画面まわりのすべて — Communities / Posts / Comments の Router、Jinja2 テンプレート（ページとコンポーネント）、共有テンプレート基盤（`app/templating.py`）、`main.py` 完成版
- 学ぶ考え方: ルーターの定義順、Jinja2 の継承と include・マクロの使い分け、HTMX の部分描画（エンドポイントの分離）、カスタムフィルターの置き場所

### 前提

- 第5章までが終わっていること（認証 Router と `get_current_user` / `require_auth`、ベーステンプレートがあること）
- ホーム（`templates/posts/home.html`）とプロフィール（`templates/accounts/profile.html`）のテンプレートは第7章で作成します。この章では Router までを完成させ、2ページの動作確認は第7章の後に行います

### 全体の中での位置

この章は **Web 層** を作る章です。第4章の Service を呼び、第5章の認証部品を使い、ブラウザへ HTML を返すところまでを通します。第1章から作ってきた3層構造が、ここで初めて1本につながります。

なお、Router 4件の全文は全コード付録 3（appendix_code_03）に、テンプレート18件の全文は全コード付録 4（appendix_code_04）に、共有基盤 `app/templating.py` は全コード付録 1（appendix_code_01）に収録しています。

---

## 6-1　FastAPI の画面実装の構造

FastAPI での画面実装は以下の流れです。

```
ブラウザ → GET /r/elixir
             ↓
         Router（app/communities/router.py）
             ↓
         Service 層（communities/services.py）
             ↓
         Jinja2 テンプレート（templates/communities/subreddit.html）
             ↓
         HTML をブラウザに返す

ブラウザ → POST /r/elixir/join  （HTMX からの部分リクエスト）
             ↓
         Router
             ↓
         Service 層
             ↓
         部分 HTML を返す（ボタン部分だけ）
             ↓
         HTMX が該当部分だけ差し替える
```

通常のリクエストでは完全な HTML を返し、HTMX からのリクエストでは部分 HTML を返します。この切り替えはヘッダーを見て行うのではなく、**エンドポイント自体を分ける**ことで実現します（ページ表示用は完全な HTML を返すエンドポイント、Join や追加読み込みなどの部分更新用は部分 HTML を返す別エンドポイント）。

---

## 6-2　Communities Router

```python
# app/communities/router.py
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_auth
from app.communities import services
from app.communities.schemas import SubredditCreate
from app.posts.services import list_posts

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# Subreddit ページ
# ----------------------------------------------------------------

@router.get("/r/{name}", response_class=HTMLResponse)
async def subreddit_page(
    request: Request,
    name: str,
    sort: str = "hot",
    page: int = 1,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404, detail=f"r/{name} は存在しません")

    posts = await list_posts(db, subreddit.id, sort, page)
    joined = False
    if current_user:
        joined = await services.is_member(db, current_user.id, subreddit.id)

    return templates.TemplateResponse(
        "communities/subreddit.html",
        {
            "request": request,
            "current_user": current_user,
            "subreddit": subreddit,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": len(posts) == 25,
            "joined": joined
        }
    )


# ----------------------------------------------------------------
# もっと見る（HTMX）
# ----------------------------------------------------------------

@router.get("/r/{name}/posts", response_class=HTMLResponse)
async def load_more_posts(
    request: Request,
    name: str,
    sort: str = "hot",
    page: int = 1,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """HTMX からの追加読み込みリクエスト"""
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    posts = await list_posts(db, subreddit.id, sort, page)

    return templates.TemplateResponse(
        "components/post_list.html",
        {
            "request": request,
            "current_user": current_user,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": len(posts) == 25,
            "subreddit": subreddit
        }
    )


# ----------------------------------------------------------------
# Join / Leave（HTMX）
# ----------------------------------------------------------------

@router.post("/r/{name}/join", response_class=HTMLResponse)
async def join_subreddit(
    request: Request,
    name: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    try:
        await services.join_subreddit(db, current_user.id, subreddit.id)
    except ValueError:
        pass   # すでに参加済みは無視する

    # Join ボタン → 参加中ボタンに差し替える HTML を返す
    return templates.TemplateResponse(
        "components/join_button.html",
        {
            "request": request,
            "subreddit": subreddit,
            "joined": True
        }
    )


@router.post("/r/{name}/leave", response_class=HTMLResponse)
async def leave_subreddit(
    request: Request,
    name: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await services.get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    try:
        await services.leave_subreddit(db, current_user.id, subreddit.id)
        joined = False
    except ValueError as e:
        # オーナーは脱退できない
        joined = True

    return templates.TemplateResponse(
        "components/join_button.html",
        {
            "request": request,
            "subreddit": subreddit,
            "joined": joined
        }
    )


# ----------------------------------------------------------------
# Subreddit 作成
# ----------------------------------------------------------------

@router.get("/subreddits/new", response_class=HTMLResponse)
async def new_subreddit_page(
    request: Request,
    current_user=Depends(require_auth)
):
    return templates.TemplateResponse(
        "communities/new_subreddit.html",
        {"request": request, "current_user": current_user, "errors": {}}
    )


@router.post("/subreddits/new")
async def create_subreddit(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    errors = {}

    try:
        data = SubredditCreate(name=name, description=description or None)
    except Exception as e:
        for error in e.errors():
            errors[error["loc"][0]] = error["msg"]
        return templates.TemplateResponse(
            "communities/new_subreddit.html",
            {"request": request, "current_user": current_user,
             "errors": errors, "name": name, "description": description},
            status_code=422
        )

    try:
        subreddit = await services.create_subreddit(db, data, current_user.id)
    except ValueError as e:
        errors["name"] = str(e)
        return templates.TemplateResponse(
            "communities/new_subreddit.html",
            {"request": request, "current_user": current_user,
             "errors": errors, "name": name, "description": description},
            status_code=422
        )

    return RedirectResponse(url=f"/r/{subreddit.name}", status_code=303)
```

**読み解き**

この Router で大切なのは、「完全な HTML を返すエンドポイント」と「部分 HTML を返すエンドポイント」を分けていることです。ページ表示（`GET /r/{name}`）は画面全体を返し、もっと見る（`GET /r/{name}/posts`）と Join / Leave（`POST .../join`・`.../leave`）は、差し替えに使う部品だけを返します。

「HTMX からのリクエストかどうか」をヘッダーで判定して1つのエンドポイントで振り分ける方法もありますが、本書では URL の時点で応答の形が決まる分け方を選びました。どの URL が何を返すかがコードの並びから読み取れ、テンプレートとの対応も追いやすくなります。部分更新のエンドポイントは「完全なページとしては表示しない」ことが前提で、返すテンプレートもコンポーネント側（`components/...`）に置かれています。

もう1つ、Service との分担も確認しておきます。Router がしているのは、値の受け取り、Service の呼び出し、結果に応じた応答（画面・部分 HTML・404・リダイレクト）の選択だけです。「すでに参加済みは無視する」のようなルールの扱いも、Service が投げた `ValueError` をどう画面に反映するか、という形で書かれています。

---

## 6-3　Subreddit ページのテンプレート

```html
<!-- templates/communities/subreddit.html -->
{% extends "base.html" %}
{% from "components/post_card.html" import post_card %}

{% block title %}r/{{ subreddit.name }} · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 py-4 flex gap-4">

  <!-- メインカラム -->
  <div class="flex-1">

    <!-- ソートタブ -->
    <div class="bg-white border border-gray-200 rounded p-2 mb-4 flex gap-2">
      <a href="/r/{{ subreddit.name }}?sort=hot"
        class="{{ 'px-4 py-1 rounded bg-gray-200 font-bold text-sm' if sort == 'hot'
                  else 'px-4 py-1 rounded hover:bg-gray-100 text-sm text-gray-600' }}">
        🔥 Hot
      </a>
      <a href="/r/{{ subreddit.name }}?sort=new"
        class="{{ 'px-4 py-1 rounded bg-gray-200 font-bold text-sm' if sort == 'new'
                  else 'px-4 py-1 rounded hover:bg-gray-100 text-sm text-gray-600' }}">
        ✨ New
      </a>
    </div>

    <!-- 投稿一覧 -->
    <div id="post-list">
      {% include "components/post_list.html" %}
    </div>

  </div>

  <!-- サイドバー -->
  <div class="w-72 shrink-0">
    <div class="bg-white border border-gray-200 rounded p-4">
      <h2 class="font-bold text-lg mb-2">r/{{ subreddit.name }}</h2>

      {% if subreddit.description %}
        <p class="text-sm text-gray-600 mb-4">{{ subreddit.description }}</p>
      {% endif %}

      <!-- Join / Leave ボタン -->
      {% if current_user %}
        <div id="join-button">
          {% include "components/join_button.html" %}
        </div>

        <a href="/r/{{ subreddit.name }}/submit"
          class="block w-full mt-2 border border-gray-300 text-center
                 rounded-full py-1 text-sm hover:bg-gray-50">
          投稿する
        </a>
      {% endif %}
    </div>
  </div>

</div>

<!-- 報告モーダル -->
{% include "components/report_modal.html" %}

{% endblock %}
```

**読み解き**

このテンプレートには、Jinja2 の再利用の方法が3種類とも出てきます。使い分けを押さえておきます。

- `{% extends "base.html" %}` は**継承**です。共通の枠（ナビゲーションバーなど）を親から受け継ぎ、`{% block %}` の中身だけを差し替えます（第5章 5-5）。
- `{% include "..." %}` は**埋め込み**です。その場に、別のテンプレートを現在の変数のまま差し込みます。`post_list.html` や `join_button.html`、報告モーダルはこの方法で置かれています。
- `{% from "..." import post_card %}` は**マクロ**の読み込みです。マクロは「引数を受け取って HTML を返す関数」で、使う側は `{{ post_card(post, current_user, ...) }}` のように呼び出します。

include とマクロの違いは「変数の渡り方」です。include された側は、呼び出し元で見えている変数をそのまま使えます。一方マクロは、原則として引数で渡された変数だけが見えます。マクロにすると「このコンポーネントは何があれば描けるか」が引数に明記されるため、置き場所を変えても壊れにくくなります。`post_card` がマクロになっているのは、ホーム・コミュニティ・詳細・検索・プロフィールと、置き場所が多いからです（第6章後編・第7章で使います）。

---

## 6-4　Join ボタンコンポーネント

```html
<!-- templates/components/join_button.html -->
{% if joined %}
  <button
    hx-post="/r/{{ subreddit.name }}/leave"
    hx-target="#join-button"
    hx-swap="innerHTML"
    class="w-full border border-blue-500 text-blue-500 rounded-full
           py-1 text-sm hover:bg-blue-50"
  >
    参加中
  </button>
{% else %}
  <button
    hx-post="/r/{{ subreddit.name }}/join"
    hx-target="#join-button"
    hx-swap="innerHTML"
    class="w-full bg-blue-500 text-white rounded-full
           py-1 text-sm hover:bg-blue-600"
  >
    参加する
  </button>
{% endif %}
```

**読み解き**

```html
hx-post="/r/elixir/join"   ← クリックで POST リクエストを送る
hx-target="#join-button"   ← レスポンスをこの要素に入れる
hx-swap="innerHTML"        ← 要素の中身を差し替える
```

Join ボタンを押すと HTMX が `/r/elixir/join` に POST を送ります。サーバーは「参加中ボタン」の HTML を返し、HTMX が `#join-button` の中身を差し替えます。ページ全体の再読み込みは不要です。

---

## 6-5　投稿リストコンポーネント

```html
<!-- templates/components/post_list.html -->
{% from "components/post_card.html" import post_card %}

{% if posts %}
  {% for post in posts %}
    {{ post_card(post, current_user, show_subreddit=False) }}
  {% endfor %}

  {% if has_more %}
    <div class="text-center py-4"
      hx-get="/r/{{ subreddit.name }}/posts?sort={{ sort }}&page={{ page + 1 }}"
      hx-trigger="revealed"
      hx-target="this"
      hx-swap="outerHTML"
    >
      <button class="px-6 py-2 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50">
        もっと見る
      </button>
    </div>
  {% endif %}
{% else %}
  <p class="text-gray-500 text-center py-8">まだ投稿がありません</p>
{% endif %}
```

**読み解き**

```html
hx-trigger="revealed"  ← 要素がスクロールで見えたときに発火
```

`revealed` トリガーを使うと、「もっと見る」ボタンが画面に表示されたとき自動的に次のページを読み込みます。ユーザーがボタンをクリックしなくても無限スクロールのように動作します。

---

## 6-6　Subreddit 作成テンプレート

```html
<!-- templates/communities/new_subreddit.html -->
{% extends "base.html" %}

{% block title %}コミュニティを作成 · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto mt-12 px-4">
  <h1 class="text-2xl font-bold mb-6">コミュニティを作成</h1>

  <form action="/subreddits/new" method="post"
    class="bg-white border border-gray-200 rounded p-6 space-y-4">
    <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        コミュニティ名
      </label>
      <input type="text" name="name"
        value="{{ name | default('') }}"
        placeholder="例: elixir"
        class="w-full border {% if errors.name %}border-red-400{% else %}border-gray-300{% endif %}
               rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
      />
      <p class="text-xs text-gray-400 mt-1">英数字とアンダースコアのみ・3〜21文字</p>
      {% if errors.name %}
        <p class="text-red-500 text-xs mt-1">{{ errors.name }}</p>
      {% endif %}
    </div>

    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">
        説明（任意）
      </label>
      <textarea name="description" rows="3"
        placeholder="このコミュニティは何について話す場所ですか？"
        class="w-full border border-gray-300 rounded px-3 py-2 text-sm
               focus:outline-none focus:border-blue-400 resize-none"
      >{{ description | default('') }}</textarea>
    </div>

    <button type="submit"
      class="w-full bg-blue-500 text-white rounded py-2 text-sm font-medium hover:bg-blue-600">
      コミュニティを作成する
    </button>

  </form>
</div>
{% endblock %}
```

---

## まとめ（前編）

```
✅ Router → Service → Template の流れを実装した
✅ 通常リクエスト用と HTMX 部分更新用でエンドポイントを分けた
✅ Join/Leave ボタンを HTMX で部分更新した
✅ hx-trigger="revealed" で無限スクロールを実装した
```

中編では Posts Router と投稿詳細ページを実装します。
