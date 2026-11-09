# 第6章　画面実装（後編）— Comments + Search

---

## 6-10　Comments Router

```python
# app/comments/router.py
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.dependencies import get_current_user, require_auth
from app.comments import services
from app.posts.services import get_post

from app.templating import templates

router = APIRouter()


# ----------------------------------------------------------------
# コメント投稿
# ----------------------------------------------------------------

@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: uuid.UUID,
    body: str = Form(...),
    parent_id: str = Form(""),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    post = await get_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=404)

    if parent_id:
        try:
            parent_uuid = uuid.UUID(parent_id)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="parent_id の形式が正しくありません"
            )
    else:
        parent_uuid = None

    try:
        await services.create_comment(
            db,
            body=body,
            author_id=current_user.id,
            post_id=post_id,
            parent_id=parent_uuid
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return RedirectResponse(
        url=f"/r/{post.subreddit.name}/{post_id}",
        status_code=303
    )


# ----------------------------------------------------------------
# コメントへの投票（HTMX）
# ----------------------------------------------------------------

@router.post("/comments/{comment_id}/vote", response_class=HTMLResponse)
async def vote_comment(
    request: Request,
    comment_id: uuid.UUID,
    value: int = Form(...),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    try:
        comment = await services.vote_comment(db, current_user.id, comment_id, value)
    except ValueError as e:
        return HTMLResponse(
            content=f'<span class="text-red-500 text-xs">{str(e)}</span>',
            status_code=400
        )

    return templates.TemplateResponse(
        "components/vote_buttons.html",
        {
            "request": request,
            "target_type": "comment",
            "target_id": str(comment_id),
            "score": comment.score,
            "current_user": current_user
        }
    )


# ----------------------------------------------------------------
# コメントの削除
# ----------------------------------------------------------------

@router.post("/comments/{comment_id}/delete")
async def delete_comment(
    request: Request,
    comment_id: uuid.UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    # subreddit_id は Referer ヘッダーから投稿ページへリダイレクト
    referer = request.headers.get("referer", "/")

    # コメントを取得して subreddit_id を確認する
    from sqlalchemy import select
    from app.comments.models import Comment
    from app.posts.models import Post

    result = await db.execute(
        select(Comment, Post.subreddit_id)
        .join(Post, Post.id == Comment.post_id)
        .where(Comment.id == comment_id)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404)

    comment, subreddit_id = row

    try:
        await services.delete_comment(db, comment_id, current_user.id, subreddit_id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="削除する権限がありません")

    return RedirectResponse(url=referer, status_code=303)


# ----------------------------------------------------------------
# 報告（HTMX）
# ----------------------------------------------------------------

@router.post("/reports", response_class=HTMLResponse)
async def create_report(
    request: Request,
    target_type: str = Form(...),
    target_id: str = Form(...),
    reason: str = Form(...),
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db)
):
    from app.reports.services import create_report as _create_report

    try:
        await _create_report(
            db,
            reporter_id=current_user.id,
            target_type=target_type,
            target_id=uuid.UUID(target_id),
            reason=reason
        )
    except ValueError as e:
        return HTMLResponse(
            content=f'<p class="text-red-500 text-sm">{str(e)}</p>',
            status_code=400
        )

    # 報告成功 → モーダルを閉じる HTML を返す
    return HTMLResponse(
        content='<p class="text-green-600 text-sm text-center py-2">報告しました。ご協力ありがとうございます。</p>'
    )
```

---

## 6-11　投票ボタンコンポーネント

```html
<!-- templates/components/vote_buttons.html -->
<div class="flex flex-col items-center gap-0.5">
  <button
    hx-post="/{{ target_type }}s/{{ target_id }}/vote"
    hx-vals='{"value": 1}'
    hx-target="#{{ target_type }}-vote-{{ target_id }}"
    hx-swap="innerHTML"
    class="text-gray-400 hover:text-orange-500 text-sm"
  >▲</button>

  <span class="text-xs font-bold text-gray-700">{{ score }}</span>

  <button
    hx-post="/{{ target_type }}s/{{ target_id }}/vote"
    hx-vals='{"value": -1}'
    hx-target="#{{ target_type }}-vote-{{ target_id }}"
    hx-swap="innerHTML"
    class="text-gray-400 hover:text-blue-500 text-sm"
  >▼</button>
</div>
```

**読み解き**

このコンポーネントは、投票への応答専用のテンプレートです。投稿への投票（6-7）とコメントへの投票（6-10）のどちらのエンドポイントも、処理の後にこのテンプレートへ `target_type`・`target_id`・`score` を渡して描画し、その HTML を返します。HTMX 側は `hx-target="#post-vote-{ID}"` / `"#comment-vote-{ID}"` の中身と差し替えます。「種類 - vote - 対象の ID」という要素 ID の約束を、ボタンを置く側（PostCard や CommentTree）と応答側（このコンポーネント）でそろえることで、ページのどこにある投票欄でも同じ仕組みで差し替えられます。`hx-post="/{{ target_type }}s/{{ target_id }}/vote"` のように URL も変数から組み立てるため、投稿用とコメント用でテンプレートを分ける必要がありません。

---

## 6-12　PostCard コンポーネント

```html
<!-- templates/components/post_card.html -->
{% macro post_card(post, current_user, show_subreddit=True) %}
<div class="bg-white border border-gray-200 rounded hover:border-gray-400 mb-2 flex">

  <!-- 投票エリア -->
  <div class="bg-gray-50 w-10 flex flex-col items-center py-2 gap-1 rounded-l"
    id="post-vote-{{ post.id }}">
    <button
      hx-post="/posts/{{ post.id }}/vote"
      hx-vals='{"value": 1}'
      hx-target="#post-vote-{{ post.id }}"
      hx-swap="innerHTML"
      class="text-gray-400 hover:text-orange-500"
    >▲</button>
    <span class="text-xs font-bold text-gray-700">{{ post.score }}</span>
    <button
      hx-post="/posts/{{ post.id }}/vote"
      hx-vals='{"value": -1}'
      hx-target="#post-vote-{{ post.id }}"
      hx-swap="innerHTML"
      class="text-gray-400 hover:text-blue-500"
    >▼</button>
  </div>

  <!-- 投稿内容 -->
  <div class="p-2 flex-1">

    <div class="flex items-start gap-2">
      <a href="/r/{{ post.subreddit.name }}/{{ post.id }}"
        class="text-sm font-medium text-gray-900 hover:underline flex-1">
        {{ post.title }}
      </a>

      {% if post.type == "link" %}
        <a href="{{ post.url }}" target="_blank" rel="noopener noreferrer"
          class="text-xs text-blue-500 hover:underline whitespace-nowrap">
          {{ post.url | urlparse_host }} ↗
        </a>
      {% else %}
        <span class="text-xs text-gray-400">text</span>
      {% endif %}
    </div>

    <div class="flex items-center gap-2 mt-1 text-xs text-gray-500">
      {% if show_subreddit %}
        <a href="/r/{{ post.subreddit.name }}" class="font-medium hover:underline">
          r/{{ post.subreddit.name }}
        </a>
        <span>•</span>
      {% endif %}
      <span>
        投稿者
        <a href="/u/{{ post.author.username }}" class="hover:underline">
          u/{{ post.author.username }}
        </a>
      </span>
      <span>•</span>
      <span>{{ post.inserted_at | time_ago }}</span>
    </div>

    <div class="mt-1 flex items-center gap-2">
      <a href="/r/{{ post.subreddit.name }}/{{ post.id }}"
        class="text-xs text-gray-500 hover:bg-gray-100 px-1 py-0.5 rounded">
        💬 {{ post.comment_count }} コメント
      </a>

      {% if current_user and current_user.id != post.author_id %}
        <button
          onclick="openReportModal('post', '{{ post.id }}')"
          class="text-xs text-gray-400 hover:text-gray-600">
          報告
        </button>
      {% endif %}
    </div>

  </div>
</div>
{% endmacro %}
```

---

## 6-13　CommentTree コンポーネント

```html
<!-- templates/components/comment_tree.html -->
{% macro comment_tree(comment, current_user, subreddit_id, depth=0) %}
<div class="mb-2 {% if depth > 0 %}border-l border-gray-200 pl-3{% endif %}">

  <div class="flex gap-2">

    <!-- 投票ボタン -->
    <div id="comment-vote-{{ comment.id }}"
      class="flex flex-col items-center gap-0.5 pt-1 shrink-0">
      <button
        hx-post="/comments/{{ comment.id }}/vote"
        hx-vals='{"value": 1}'
        hx-target="#comment-vote-{{ comment.id }}"
        hx-swap="innerHTML"
        class="text-gray-300 hover:text-orange-500 text-xs"
      >▲</button>
      <span class="text-xs text-gray-500">{{ comment.score }}</span>
      <button
        hx-post="/comments/{{ comment.id }}/vote"
        hx-vals='{"value": -1}'
        hx-target="#comment-vote-{{ comment.id }}"
        hx-swap="innerHTML"
        class="text-gray-300 hover:text-blue-500 text-xs"
      >▼</button>
    </div>

    <!-- コメント内容 -->
    <div class="flex-1 border-l-2 border-gray-100 pl-2">
      <div class="text-xs text-gray-500 mb-1">
        <span class="font-medium text-gray-700">
          u/{{ comment.author.username }}
        </span>
        • {{ comment.inserted_at | time_ago }}
        • {{ comment.score }} ポイント
      </div>

      <p class="text-sm text-gray-800 whitespace-pre-wrap">{{ comment.body }}</p>

      <div class="flex gap-3 mt-1">

        {% if current_user %}
          <!-- 返信フォーム（クリックでトグル） -->
          <button
            onclick="toggleReplyForm('{{ comment.id }}')"
            class="text-xs text-gray-400 hover:text-gray-600"
          >返信</button>
        {% endif %}

        {% if current_user and current_user.id == comment.author_id %}
          <form action="/comments/{{ comment.id }}/delete" method="post" class="inline">
            <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />
            <button type="submit"
              onclick="return confirm('このコメントを削除しますか？')"
              class="text-xs text-red-400 hover:text-red-600">
              削除
            </button>
          </form>
        {% endif %}

        {% if current_user and current_user.id != comment.author_id %}
          <button
            onclick="openReportModal('comment', '{{ comment.id }}')"
            class="text-xs text-gray-400 hover:text-gray-600">
            報告
          </button>
        {% endif %}
      </div>

      <!-- 返信フォーム（デフォルト非表示） -->
      {% if current_user %}
        <div id="reply-form-{{ comment.id }}" class="hidden mt-2">
          <form action="/posts/{{ comment.post_id }}/comments" method="post">
            <input type="hidden" name="csrf_token" value="{{ request.cookies.get('csrf_token', '') }}" />
            <input type="hidden" name="parent_id" value="{{ comment.id }}" />
            <textarea name="body" rows="3"
              placeholder="返信を入力..."
              class="w-full border border-gray-300 rounded p-2 text-xs
                     resize-none focus:outline-none focus:border-blue-400"
            ></textarea>
            <div class="flex gap-2 mt-1 justify-end">
              <button type="button"
                onclick="toggleReplyForm('{{ comment.id }}')"
                class="text-xs text-gray-500 px-2 py-1">
                キャンセル
              </button>
              <button type="submit"
                class="text-xs bg-blue-500 text-white px-3 py-1 rounded hover:bg-blue-600">
                返信する
              </button>
            </div>
          </form>
        </div>
      {% endif %}

    </div>
  </div>

  <!-- 子コメント（再帰）-->
  {% if comment.children and depth < 8 %}
    <div class="ml-4 mt-2">
      {% for child in comment.children %}
        {{ comment_tree(child, current_user, subreddit_id, depth + 1) }}
      {% endfor %}
    </div>
  {% endif %}

</div>
{% endmacro %}
```

**読み解き**

返信ボタンが呼ぶ `toggleReplyForm(...)` は、このコンポーネント内ではなく **base.html の共通スクリプト（5-5）で定義**しています。すべてのページで読み込まれる base.html に置くことで、どの画面のコメントツリーでも同じ関数が使えます。「関数は、それを使うコンポーネントの中ではなく、全ページ共通の場所に1つだけ置く」という置き場所の判断です（第7章の報告モーダルでも同じ考え方を使います）。

また、呼び出し側（detail.html）では `{% from "components/comment_tree.html" import comment_tree with context %}` と `with context` 付きで import しています。これは、マクロ内のフォームが CSRF トークン（`request.cookies`）を参照するために必要な指定です（マクロは通常、呼び出し側の変数を見られません）。

このマクロは、自分自身を呼び出す**再帰マクロ**でもあります。第4章でメモリ上に組み立てたツリー（`children`）を、ここでは描画の側でたどります。`depth < 8` の条件は表示上の上限で、それより深い返信はこの画面では広げません（データとして存在しないわけではありません）。

---

## 6-14　検索テンプレート

```html
<!-- templates/posts/search.html -->
{% extends "base.html" %}
{% from "components/post_card.html" import post_card %}

{% block title %}
  {% if query %}「{{ query }}」の検索結果{% else %}検索{% endif %} · reddit_clone
{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 py-6">

  <form action="/search" method="get" class="mb-6">
    <div class="flex gap-2">
      <input type="text" name="q" value="{{ query }}"
        placeholder="キーワードを入力..."
        autofocus
        class="flex-1 border border-gray-300 rounded px-4 py-2 text-sm
               focus:outline-none focus:border-blue-400"
      />
      <button type="submit"
        class="px-4 py-2 bg-blue-500 text-white text-sm rounded hover:bg-blue-600">
        検索
      </button>
    </div>
  </form>

  {% if not query %}
    <p class="text-gray-400 text-center py-12">キーワードを入力して検索してください</p>
  {% else %}
    <h1 class="text-lg font-bold mb-4">「{{ query }}」の検索結果</h1>

    <div class="flex gap-4">

      <!-- 投稿 -->
      <div class="flex-1">
        <h2 class="text-sm font-bold text-gray-500 uppercase mb-3">
          投稿 {% if posts %}({{ posts | length }}件){% endif %}
        </h2>

        {% if posts %}
          {% for post in posts %}
            {{ post_card(post, current_user, show_subreddit=True) }}
          {% endfor %}
        {% else %}
          <div class="bg-white border border-gray-200 rounded p-6 text-center">
            <p class="text-gray-400 text-sm">投稿が見つかりませんでした</p>
          </div>
        {% endif %}
      </div>

      <!-- コミュニティ -->
      <div class="w-64 shrink-0">
        <h2 class="text-sm font-bold text-gray-500 uppercase mb-3">
          コミュニティ {% if subreddits %}({{ subreddits | length }}件){% endif %}
        </h2>

        {% if subreddits %}
          {% for subreddit in subreddits %}
            <div class="bg-white border border-gray-200 rounded p-3 mb-2 hover:border-gray-400">
              <a href="/r/{{ subreddit.name }}" class="block">
                <p class="font-medium text-sm">r/{{ subreddit.name }}</p>
                {% if subreddit.description %}
                  <p class="text-xs text-gray-400 mt-1 truncate">
                    {{ subreddit.description }}
                  </p>
                {% endif %}
              </a>
            </div>
          {% endfor %}
        {% else %}
          <div class="bg-white border border-gray-200 rounded p-4 text-center">
            <p class="text-gray-400 text-sm">見つかりませんでした</p>
          </div>
        {% endif %}
      </div>

    </div>
  {% endif %}
</div>

<!-- 報告モーダル -->
{% include "components/report_modal.html" %}

{% endblock %}
```

---

## 6-15　共有テンプレートモジュールとカスタムフィルター

テンプレートで使う `time_ago` と `urlparse_host` フィルターを登録します。

登録先には注意が必要です。これまで各 Router は自分のファイルで `Jinja2Templates(directory="templates")` を作って描画に使っていました。この状態で main.py 側の別の `Jinja2Templates` にフィルターを登録しても、**描画に使われる Router 側のオブジェクトにはフィルターが入りません**（オブジェクトが別々だからです）。

そこで、`templates` を作る場所を専用モジュール `app/templating.py` に1つだけ用意し、フィルターの登録もそこに集約します。全 Router がこの1つを共有すれば、登録したフィルターがそのまま描画に届きます。

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
```

あわせて、4つの Router すべて（第5章で作った `app/accounts/router.py` も含みます）で、自前の `Jinja2Templates` 作成をやめ、共有オブジェクトを使うよう書き換えます。

```python
# 各 Router の冒頭（変更前）
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
```

```python
# 各 Router の冒頭（変更後）
from app.templating import templates
```

---

## 6-16　main.py 完成版

フィルターの登録先が `app/templating.py` に移ったため、main.py はすっきりします。CSRF の登録（`dependencies` と ミドルウェア）は 5-9 で追加した形のままです。

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

---

## 動作確認（この章の仕上げ）

前提: サーバーが起動していて、ログインできること。ブラウザで順に確かめます。

- [ ] コミュニティを作成すると `/r/{名前}` にコミュニティページが表示され、作成者として「参加中」になっている
- [ ] 「参加する／参加中」ボタンで、ページ全体が再読み込みされずにボタンだけが差し替わる
- [ ] 投稿を作成すると詳細ページが開く。投稿への投票（▲▼）で、スコアの部分だけが差し替わる。同じ方向をもう一度押すと取り消しになる
- [ ] コメントを投稿でき、「返信」ボタンで返信フォームが開く。返信は入れ子になって表示される
- [ ] コミュニティページを下へスクロールすると、「もっと見る」で次のページ分の投稿が読み込まれる
- [ ] `/search?q=キーワード` で、投稿とコミュニティの両方の検索結果が出る
- [ ] 投稿カードの経過時間が「○分前」「○時間前」の形で表示される（`time_ago` フィルターが効いている）
- [ ] ホーム（`/`）とプロフィール（`/u/{名前}`）は、この時点ではまだ `TemplateNotFound` になるのが正しい状態である（テンプレートは第7章で作成する）

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| 投稿作成ページ（`/r/{名前}/submit`）を開くと 422 になる | ルートの定義順。`/r/{name}/{post_id}` が先に定義されていると、`submit` が `post_id` として解釈される | `/submit` のルートを `/{post_id}` より前に定義する（6-7 の読み解き） |
| ページ表示で `No filter named 'time_ago'` というエラーになる | フィルターを、描画に使われていない別の `Jinja2Templates` オブジェクトに登録している | `app/templating.py` の共有オブジェクトに登録し、全 Router がそれを共有する（6-15） |
| 詳細ページの投票ボタンの URL が `/s//vote` のように壊れて組み立てられる | `vote_buttons.html` が必要とする `target_type`・`target_id`・`score` が渡っていない | include の直前で `{% set %}` により3つの値を渡す（6-8 の読み解き） |
| 「返信」ボタンを押しても何も起きない | `toggleReplyForm` が定義されていない（コンポーネントの中には無い） | base.html の共通スクリプトで定義する（5-5・6-13） |
| コメントまわりで `request` が未定義という趣旨の描画エラーになる | `comment_tree` マクロが `request` を参照するのに、`with context` なしで import している | 呼び出し側の import に `with context` を付ける（6-13） |
| ホームを開くと `TemplateNotFound: posts/home.html` になる | テンプレートが未作成（この章では正常な状態） | 第7章 7-5 で作成する。この章では Router の完成までが目標 |

---

## 確認問題

1. 部分更新用のエンドポイントを、ページ表示用と分ける設計にしているのはなぜですか。リクエストヘッダーで HTMX かどうかを判定する方法と比べて、何が違いますか。
2. `GET /r/{name}/submit` を `GET /r/{name}/{post_id}` より後に定義すると、何が起きますか。なぜですか。
3. 詳細ページで `vote_buttons.html` を include する際、`{% set %}` で値を渡す必要があるのはなぜですか。
4. `app/templating.py` を作らず、`main.py` 側で作った `Jinja2Templates` にだけフィルターを登録すると、画面表示はどうなりますか。
5. `comment_tree` の import には `with context` が必要で、`post_card` には不要なのはなぜですか。

---

## まとめと次章へのつながり

```
✅ Comments Router（投稿・投票・削除・報告）
✅ 投票ボタンコンポーネント（HTMX）
✅ PostCard マクロコンポーネント
✅ CommentTree 再帰マクロコンポーネント
✅ 検索テンプレート
✅ Jinja2 カスタムフィルター
✅ main.py 完成版
```

なお、この章が終わった時点では、ホーム（`/`）とプロフィール（`/u/{username}`）の2ページはまだ表示できません。Router はどちらも完成していますが、テンプレート（`templates/posts/home.html` と `templates/accounts/profile.html`）は第7章 7-5・7-6 で作成するためです。この2ページの動作確認は、第7章の後に行ってください。

**この章の重要なポイント**

```
hx-post       → クリックで POST リクエストを送る
hx-target     → レスポンスを入れる要素を指定する
hx-swap       → 差し替え方法を指定する
hx-trigger    → イベントのトリガーを指定する
hx-vals       → 追加のパラメータを送る
revealed      → 要素が見えたときに発火（無限スクロール）
{% macro %}   → 再利用可能なテンプレート関数
```

次の章では HTMX の詳細な使い方と報告モーダルを実装します。あわせて、ホームとプロフィールのテンプレートを作成し、この章までで表示できなかった2ページを仕上げます。

---

## 確認問題の答え

1. URL の時点で「完全な HTML を返すのか、部分 HTML を返すのか」が決まるためです。どの URL が何を返すかがコードの並びから読み取れ、テンプレートとの対応も追いやすくなります。ヘッダーで判定する方法では、1つのエンドポイントが2種類の応答を持つことになり、読み分けが難しくなります。
2. `submit` という文字列が `{post_id}` にマッチし、UUID への変換に失敗して 422 になり、投稿作成ページが開けなくなります。FastAPI（Starlette）はルートを定義した順に照合するため、より具体的な `/submit` を先に置く必要があります。
3. `vote_buttons.html` は `target_type`・`target_id`・`score` の3変数を必要としますが、詳細ページの文脈には `post` しかなく、その3つが揃っていません。include は「その場の変数」を使う仕組みなので、直前で `{% set %}` により不足分を用意する必要があります。
4. 描画に使われるのは各 Router が持つ `templates` オブジェクトなので、別のオブジェクトへの登録は届きません。`time_ago` を使うページ（投稿カードのあるページ）で「フィルターが無い」というエラーになります。
5. `comment_tree` はマクロの中で `request`（CSRF トークンの読み取り）を参照しますが、`request` は引数にありません。呼び出し側の文脈を見せる `with context` が必要です。`post_card` は引数（`post`・`current_user`）だけで描画が完結するため、不要です。
