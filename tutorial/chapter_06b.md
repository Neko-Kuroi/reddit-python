# 第6章　画面実装（中編）— Posts

---

## 6-7　Posts Router

```python
# app/posts/router.py
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.dependencies import get_current_user, require_auth
from app.posts import services
from app.posts.schemas import PostCreate
from app.communities.services import get_subreddit_by_name
from app.comments.services import list_comments

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# 投稿作成
# ----------------------------------------------------------------

@router.get("/r/{name}/submit", response_class=HTMLResponse)
async def new_post_page(
    request: Request,
    name: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    return templates.TemplateResponse(
        "posts/new_post.html",
        {
            "request": request,
            "current_user": current_user,
            "subreddit": subreddit,
            "errors": {},
            "post_type": "text"
        }
    )


@router.post("/r/{name}/submit")
async def create_post(
    request: Request,
    name: str,
    title: str = Form(...),
    post_type: str = Form(...),
    body: str = Form(""),
    url: str = Form(""),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    subreddit = await get_subreddit_by_name(db, name)
    if subreddit is None:
        raise HTTPException(status_code=404)

    errors = {}
    try:
        data = PostCreate(
            title=title,
            type=post_type,
            body=body if post_type == "text" else None,
            url=url if post_type == "link" else None
        )
    except Exception as e:
        for error in e.errors():
            field = error["loc"][0] if error["loc"] else "general"
            errors[field] = error["msg"]
        return templates.TemplateResponse(
            "posts/new_post.html",
            {
                "request": request,
                "current_user": current_user,
                "subreddit": subreddit,
                "errors": errors,
                "post_type": post_type,
                "title": title,
                "body": body,
                "url": url
            },
            status_code=422
        )

    post = await services.create_post(db, data, current_user.id, subreddit.id)
    return RedirectResponse(url=f"/r/{name}/{post.id}", status_code=303)


# ----------------------------------------------------------------
# 投稿詳細ページ
# ----------------------------------------------------------------

@router.get("/r/{name}/{post_id}", response_class=HTMLResponse)
async def post_detail(
    request: Request,
    name: str,
    post_id: uuid.UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    post = await services.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="投稿が見つかりません")

    comments = await list_comments(db, post_id)

    return templates.TemplateResponse(
        "posts/detail.html",
        {
            "request": request,
            "current_user": current_user,
            "post": post,
            "comments": comments
        }
    )


# ----------------------------------------------------------------
# 投稿への投票（HTMX）
# ----------------------------------------------------------------

@router.post("/posts/{post_id}/vote", response_class=HTMLResponse)
async def vote_post(
    request: Request,
    post_id: uuid.UUID,
    value: int = Form(...),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    try:
        post = await services.vote_post(db, current_user.id, post_id, value)
    except ValueError as e:
        # 自分の投稿への投票など
        return HTMLResponse(
            content=f'<span class="text-red-500 text-xs">{str(e)}</span>',
            status_code=400
        )

    # 更新後のスコアと投票ボタンの HTML を返す
    return templates.TemplateResponse(
        "components/vote_buttons.html",
        {
            "request": request,
            "target_type": "post",
            "target_id": str(post_id),
            "score": post.score,
            "current_user": current_user
        }
    )


# ----------------------------------------------------------------
# 投稿の削除
# ----------------------------------------------------------------

@router.post("/posts/{post_id}/delete")
async def delete_post(
    post_id: uuid.UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    post = await services.get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404)

    subreddit_name = post.subreddit.name

    try:
        await services.delete_post(db, post_id, current_user.id, post.subreddit_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="削除する権限がありません")

    return RedirectResponse(url=f"/r/{subreddit_name}", status_code=303)


# ----------------------------------------------------------------
# ホーム Feed
# ----------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    sort: str = "hot",
    page: int = 1,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    from app.communities.services import list_joined_subreddits

    posts = await services.list_home_posts(db, current_user.id, sort, page)
    joined_subreddits = await list_joined_subreddits(db, current_user.id)

    return templates.TemplateResponse(
        "posts/home.html",
        {
            "request": request,
            "current_user": current_user,
            "posts": posts,
            "sort": sort,
            "page": page,
            "has_more": len(posts) == 25,
            "joined_subreddits": joined_subreddits
        }
    )


# ----------------------------------------------------------------
# 検索
# ----------------------------------------------------------------

@router.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = "",
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from app.communities.services import search_subreddits

    posts = await services.search_posts(db, q) if q else []
    subreddits = await search_subreddits(db, q) if q else []

    return templates.TemplateResponse(
        "posts/search.html",
        {
            "request": request,
            "current_user": current_user,
            "query": q,
            "posts": posts,
            "subreddits": subreddits
        }
    )
```

**読み解き**

ルートの定義順について。FastAPI（Starlette）はルートを**定義した順**に照合します。`GET /r/{name}/submit` と `GET /r/{name}/{post_id}` では、`submit` が `{post_id}` にもマッチしてしまうため、**`/submit` 側を先に定義**しないと投稿作成ページが詳細ページとして解釈され、422 エラーになります。この Router では Subreddit 表示 → 投稿作成（submit）→ 投稿詳細、の順に並べてあります。

投稿詳細ページの描画では、使わない変数（以前あった `reply_to` など）は渡しません。渡した値がテンプレートで使われない「死に変数」は、読み手の混乱の元になるためです。

**この時点での注意（ホーム Feed のテンプレートは第7章で作成）**

この Router の `home`（`GET /`）が描画する `templates/posts/home.html` は、まだ作っていません。ホーム Feed のテンプレートは第7章 7-5 で作成します。そのため、この章の時点では `/` を開くと `TemplateNotFound` になり、ホームの動作確認はできません（Router と Service はここで完成しています）。

同じく、プロフィール画面のテンプレート `templates/accounts/profile.html` も未作成です（Router 自体は第5章 5-4 で作成済みで、テンプレートは第7章 7-6 で作成します）。どちらのページも、第7章を終えてから動作確認してください。

---

## 6-8　投稿詳細テンプレート

```html
<!-- templates/posts/detail.html -->
{% extends "base.html" %}
{% from "components/post_card.html" import post_card %}
{% from "components/comment_tree.html" import comment_tree with context %}

{% block title %}{{ post.title }} · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-4">

  <!-- 投稿本体 -->
  <div class="bg-white border border-gray-200 rounded p-4 mb-4">
    <div class="flex gap-3">

      <!-- 投票 -->
      <div id="post-vote-{{ post.id }}" class="flex flex-col items-center gap-1">
        {% set target_type = "post" %}
        {% set target_id = post.id %}
        {% set score = post.score %}
        {% include "components/vote_buttons.html" with context %}
      </div>

      <div class="flex-1">
        <h1 class="text-xl font-bold text-gray-900 mb-1">{{ post.title }}</h1>

        <div class="text-xs text-gray-500 mb-3 flex gap-2">
          <a href="/r/{{ post.subreddit.name }}" class="hover:underline font-medium">
            r/{{ post.subreddit.name }}
          </a>
          <span>•</span>
          <a href="/u/{{ post.author.username }}" class="hover:underline">
            u/{{ post.author.username }}
          </a>
        </div>

        {% if post.type == "text" and post.body %}
          <p class="text-sm text-gray-800 whitespace-pre-wrap mb-3">{{ post.body }}</p>
        {% endif %}

        {% if post.type == "link" %}
          <a href="{{ post.url }}" target="_blank" rel="noopener noreferrer"
            class="text-sm text-blue-500 hover:underline break-all">
            {{ post.url }} ↗
          </a>
        {% endif %}

        {% if current_user and current_user.id == post.author_id %}
          <form action="/posts/{{ post.id }}/delete" method="post" class="mt-2">
            <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />
            <button type="submit"
              onclick="return confirm('この投稿を削除しますか？')"
              class="text-xs text-red-400 hover:text-red-600">
              削除
            </button>
          </form>
        {% endif %}
      </div>
    </div>
  </div>

  <!-- コメント投稿フォーム -->
  {% if current_user %}
    <div class="bg-white border border-gray-200 rounded p-4 mb-4">
      <p class="text-sm font-medium mb-2">コメントを追加</p>
      <form action="/posts/{{ post.id }}/comments" method="post">
      <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />
        <input type="hidden" name="parent_id" value="" />
        <textarea name="body" rows="4"
          placeholder="コメントを入力してください"
          class="w-full border border-gray-300 rounded p-2 text-sm resize-none
                 focus:outline-none focus:border-blue-400"
        ></textarea>
        <div class="flex justify-end mt-2">
          <button type="submit"
            class="px-4 py-1 bg-blue-500 text-white text-sm rounded hover:bg-blue-600">
            投稿する
          </button>
        </div>
      </form>
    </div>
  {% endif %}

  <!-- コメント一覧 -->
  <div class="bg-white border border-gray-200 rounded p-4">
    {% if comments %}
      {% for comment in comments %}
        {{ comment_tree(comment, current_user, post.subreddit_id, depth=0) }}
      {% endfor %}
    {% else %}
      <p class="text-gray-400 text-sm text-center py-4">
        まだコメントはありません。最初のコメントを投稿しましょう！
      </p>
    {% endif %}
  </div>

</div>

<!-- 報告モーダル -->
{% include "components/report_modal.html" %}

{% endblock %}
```

**読み解き**

投票ボタンのコンポーネント（`components/vote_buttons.html`）は `target_type`・`target_id`・`score` という3つの変数を必要とします。PostCard マクロ経由の表示ではマクロの引数から値が渡りますが、この詳細ページでは直接 include するため、include の直前で `{% set %}` により明示的に渡します。これを忘れると投票先の URL が組み立てられず、投票ボタンが機能しません（実際に、URL が `/s//vote` のように壊れた形で組み立てられてしまう失敗が起きやすい箇所です）。

末尾の報告モーダルの include は、このページにも報告ボタン（PostCard・コメント）があるため必要です。報告ボタンのあるページすべてに include するのが約束です（第7章 7-3 も参照）。

もう1つ、このテンプレートの冒頭にある `{% from "components/comment_tree.html" import comment_tree with context %}` の `with context` に注意してください。マクロは原則として引数の変数だけが見えますが、`comment_tree` の中では CSRF トークンを読むために `request` を使っています。`request` は引数に無いので、呼び出し側の文脈（変数一式）も見えるようにする `with context` が必要です。逆に `post_card` は引数だけで完結しているため、`with context` は付けません。「マクロの中で、引数以外の変数を使っているか」が判断の基準です。

---

## 6-9　投稿作成テンプレート

```html
<!-- templates/posts/new_post.html -->
{% extends "base.html" %}

{% block title %}r/{{ subreddit.name }} に投稿する · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto mt-8 px-4">
  <h1 class="text-xl font-bold mb-4">r/{{ subreddit.name }} に投稿する</h1>

  <!-- タブ切り替え -->
  <div class="flex border-b border-gray-200 mb-4" id="type-tabs">
    <button
      onclick="switchType('text')"
      id="tab-text"
      class="px-6 py-2 text-sm font-bold border-b-2 border-blue-500 text-blue-500"
    >
      📝 テキスト
    </button>
    <button
      onclick="switchType('link')"
      id="tab-link"
      class="px-6 py-2 text-sm text-gray-500 hover:text-gray-700"
    >
      🔗 リンク
    </button>
  </div>

  <form action="/r/{{ subreddit.name }}/submit" method="post"
    class="bg-white border border-gray-200 rounded p-4 space-y-4">
    <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />

    <input type="hidden" name="post_type" id="post_type" value="{{ post_type }}" />

    <div>
      <input type="text" name="title"
        value="{{ title | default('') }}"
        placeholder="タイトルを入力してください"
        class="w-full border {% if errors.title %}border-red-400{% else %}border-gray-300{% endif %}
               rounded px-3 py-2 text-sm focus:outline-none focus:border-blue-400"
      />
      {% if errors.title %}
        <p class="text-red-500 text-xs mt-1">{{ errors.title }}</p>
      {% endif %}
    </div>

    <!-- テキスト入力欄 -->
    <div id="body-section">
      <textarea name="body" rows="6"
        placeholder="本文を入力してください"
        class="w-full border border-gray-300 rounded px-3 py-2 text-sm
               focus:outline-none focus:border-blue-400 resize-none"
      >{{ body | default('') }}</textarea>
    </div>

    <!-- URL 入力欄 -->
    <div id="url-section" class="hidden">
      <input type="url" name="url"
        value="{{ url | default('') }}"
        placeholder="https://example.com"
        class="w-full border border-gray-300 rounded px-3 py-2 text-sm
               focus:outline-none focus:border-blue-400"
      />
      {% if errors.url %}
        <p class="text-red-500 text-xs mt-1">{{ errors.url }}</p>
      {% endif %}
    </div>

    {% if errors.general %}
      <p class="text-red-500 text-xs">{{ errors.general }}</p>
    {% endif %}

    <div class="flex justify-end gap-2">
      <a href="/r/{{ subreddit.name }}"
        class="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50">
        キャンセル
      </a>
      <button type="submit"
        class="px-4 py-2 text-sm bg-blue-500 text-white rounded hover:bg-blue-600">
        投稿する
      </button>
    </div>

  </form>
</div>

<script>
  function switchType(type) {
    document.getElementById("post_type").value = type;

    const tabText = document.getElementById("tab-text");
    const tabLink = document.getElementById("tab-link");
    const bodySection = document.getElementById("body-section");
    const urlSection = document.getElementById("url-section");

    const activeClass = "px-6 py-2 text-sm font-bold border-b-2 border-blue-500 text-blue-500";
    const inactiveClass = "px-6 py-2 text-sm text-gray-500 hover:text-gray-700";

    if (type === "text") {
      tabText.className = activeClass;
      tabLink.className = inactiveClass;
      bodySection.classList.remove("hidden");
      urlSection.classList.add("hidden");
    } else {
      tabText.className = inactiveClass;
      tabLink.className = activeClass;
      bodySection.classList.add("hidden");
      urlSection.classList.remove("hidden");
    }
  }

  // 再表示時（バリデーションエラーなど）も現在の post_type に合わせる
  switchType("{{ post_type }}");
</script>
{% endblock %}
```

---

## まとめ（中編）

```
✅ Posts Router を実装した
✅ 投稿詳細・作成ページのテンプレートを実装した
✅ 投票を HTMX で部分更新した
✅ タブ切り替えを最小限の JavaScript で実装した
✅ ホーム Feed と検索のエンドポイントを実装した
```

後編では Comments Router と Search テンプレートを実装します。
