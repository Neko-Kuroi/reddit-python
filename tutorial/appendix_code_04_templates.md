# 全コード付録 4　テンプレート（Jinja2）

> **このファイルは自動生成です。** 生成スクリプト `~/workspace/reddit_clone_audit/generate_code_appendix_py.py` が、
> 正本のコードファイル（`~/workspace/reddit_clone_python/` 内）から全文を機械的に転記して作りました。
> **正本はコードファイルそのもの**であり、この付録は「すべてのコードがチュートリアル側に収録されている」
> ことを保証するための再録です。コードを直すときは正本を直し、この付録は再生成してください。
>
> 対応する章: 第5章（土台と認証画面）、第6章（各画面とコンポーネント）、第7章（モーダル・ホーム・プロフィール）

---

## templates/base.html

対応: 第5章。正本: `templates/base.html`

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

## templates/404.html

対応: 第5章。正本: `templates/404.html`

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

## templates/accounts/register.html

対応: 第5章。正本: `templates/accounts/register.html`

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

## templates/accounts/login.html

対応: 第5章。正本: `templates/accounts/login.html`

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

## templates/accounts/profile.html

対応: 第7章。正本: `templates/accounts/profile.html`

```html
<!-- templates/accounts/profile.html -->
{% extends "base.html" %}
{% from "components/post_card.html" import post_card %}

{% block title %}u/{{ profile_user.username }} · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">

  <!-- ユーザー情報 -->
  <div class="bg-white border border-gray-200 rounded p-6 mb-4">
    <h1 class="text-2xl font-bold text-gray-900">
      u/{{ profile_user.username }}
    </h1>
    <p class="text-sm text-gray-400 mt-1">
      {{ profile_user.inserted_at.year }}年{{ profile_user.inserted_at.month }}月に登録
    </p>

    <!-- Karma -->
    <div class="flex gap-6 mt-4 pt-4 border-t border-gray-100">
      <div class="text-center">
        <p class="text-xl font-bold text-gray-800">
          {{ profile_user.post_karma | format_karma }}
        </p>
        <p class="text-xs text-gray-400">Post Karma</p>
      </div>
      <div class="text-center">
        <p class="text-xl font-bold text-gray-800">
          {{ profile_user.comment_karma | format_karma }}
        </p>
        <p class="text-xs text-gray-400">Comment Karma</p>
      </div>
      <div class="text-center">
        <p class="text-xl font-bold text-gray-800">
          {{ (profile_user.post_karma + profile_user.comment_karma) | format_karma }}
        </p>
        <p class="text-xs text-gray-400">合計 Karma</p>
      </div>
    </div>
  </div>

  <!-- 投稿一覧 -->
  <h2 class="text-sm font-bold text-gray-500 uppercase mb-3">投稿</h2>

  {% if posts %}
    {% for post in posts %}
      {{ post_card(post, current_user, show_subreddit=True) }}
    {% endfor %}
  {% else %}
    <div class="bg-white border border-gray-200 rounded p-8 text-center">
      <p class="text-gray-400 text-sm">まだ投稿がありません</p>
    </div>
  {% endif %}

</div>

<!-- 報告モーダル -->
{% include "components/report_modal.html" %}

{% endblock %}
```

## templates/communities/subreddit.html

対応: 第6章。正本: `templates/communities/subreddit.html`

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

## templates/communities/new_subreddit.html

対応: 第6章。正本: `templates/communities/new_subreddit.html`

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

## templates/posts/detail.html

対応: 第6章。正本: `templates/posts/detail.html`

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

## templates/posts/new_post.html

対応: 第6章。正本: `templates/posts/new_post.html`

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

## templates/posts/home.html

対応: 第7章。正本: `templates/posts/home.html`

```html
<!-- templates/posts/home.html -->
{% extends "base.html" %}
{% from "components/post_card.html" import post_card %}

{% block title %}ホーム · reddit_clone{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 py-4 flex gap-4">

  <!-- 左サイドバー -->
  <div class="w-48 shrink-0">
    <div class="bg-white border border-gray-200 rounded p-3">
      <h2 class="text-xs font-bold text-gray-500 uppercase mb-2">参加中</h2>

      {% if joined_subreddits %}
        {% for subreddit in joined_subreddits %}
          <a href="/r/{{ subreddit.name }}"
            class="block text-sm py-1 hover:text-blue-500 truncate">
            r/{{ subreddit.name }}
          </a>
        {% endfor %}
      {% else %}
        <p class="text-xs text-gray-400">まだ参加していません</p>
      {% endif %}

      <div class="border-t border-gray-100 mt-3 pt-3">
        <a href="/subreddits/new"
          class="text-sm text-blue-500 hover:underline">
          ＋ コミュニティを作成
        </a>
      </div>
    </div>
  </div>

  <!-- メインカラム -->
  <div class="flex-1">

    <!-- ソートタブ -->
    <div class="bg-white border border-gray-200 rounded p-2 mb-4 flex gap-2">
      <a href="/?sort=hot"
        class="{{ 'px-4 py-1 rounded bg-gray-200 font-bold text-sm' if sort == 'hot'
                  else 'px-4 py-1 rounded hover:bg-gray-100 text-sm text-gray-600' }}">
        🔥 Hot
      </a>
      <a href="/?sort=new"
        class="{{ 'px-4 py-1 rounded bg-gray-200 font-bold text-sm' if sort == 'new'
                  else 'px-4 py-1 rounded hover:bg-gray-100 text-sm text-gray-600' }}">
        ✨ New
      </a>
    </div>

    <!-- 投稿一覧 -->
    {% if posts %}
      {% for post in posts %}
        {{ post_card(post, current_user, show_subreddit=True) }}
      {% endfor %}

      {% if has_more %}
        <div class="text-center py-4">
          <a href="/?sort={{ sort }}&page={{ page + 1 }}"
            class="px-6 py-2 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50">
            もっと見る
          </a>
        </div>
      {% endif %}

    {% else %}
      <div class="bg-white border border-gray-200 rounded p-8 text-center">
        <p class="text-gray-500 mb-2">まだ投稿がありません</p>
        <p class="text-sm text-gray-400">コミュニティに参加して投稿を見てみましょう</p>
        <a href="/subreddits/new"
          class="inline-block mt-4 px-4 py-2 bg-blue-500 text-white text-sm
                 rounded hover:bg-blue-600">
          コミュニティを作成
        </a>
      </div>
    {% endif %}

  </div>
</div>

<!-- 報告モーダル -->
{% include "components/report_modal.html" %}

{% endblock %}
```

## templates/posts/search.html

対応: 第6章。正本: `templates/posts/search.html`

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

## templates/components/join_button.html

対応: 第6章。正本: `templates/components/join_button.html`

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

## templates/components/post_list.html

対応: 第6章。正本: `templates/components/post_list.html`

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

## templates/components/vote_buttons.html

対応: 第6章。正本: `templates/components/vote_buttons.html`

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

## templates/components/post_card.html

対応: 第6章。正本: `templates/components/post_card.html`

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

## templates/components/comment_tree.html

対応: 第6章。正本: `templates/components/comment_tree.html`

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

## templates/components/report_modal.html

対応: 第7章。正本: `templates/components/report_modal.html`

```html
<!-- templates/components/report_modal.html -->
<!-- ページの末尾に1つだけ配置する -->

<!-- 背景オーバーレイ（クリックで閉じる） -->
<div id="report-overlay"
  class="hidden fixed inset-0 bg-black bg-opacity-50 z-40"
  onclick="closeReportModal()"
></div>

<!-- モーダル本体 -->
<div id="report-modal"
  class="hidden fixed inset-0 z-50 flex items-center justify-center p-4"
>
  <div class="bg-white rounded-lg shadow-xl w-full max-w-md">

    <!-- ヘッダー -->
    <div class="flex justify-between items-center p-4 border-b border-gray-200">
      <h2 class="text-lg font-bold">報告する</h2>
      <button onclick="closeReportModal()"
        class="text-gray-400 hover:text-gray-600 text-xl">✕</button>
    </div>

    <!-- 報告フォーム -->
    <div class="p-4">
      <p class="text-sm text-gray-600 mb-3">報告する理由を選択してください</p>

      <!-- hidden フィールド（JavaScript でセットする） -->
      <!-- hx-include は name 属性のある要素の値を集めるため、name が必須 -->
      <input type="hidden" id="report-target-type" name="target_type" value="" />
      <input type="hidden" id="report-target-id" name="target_id" value="" />

      <div class="space-y-2" id="report-result">
        {% for value, label in report_reasons %}
          <button
            hx-post="/reports"
            hx-include="#report-target-type, #report-target-id"
            hx-vals='{"reason": "{{ value }}"}'
            hx-target="#report-result"
            hx-swap="innerHTML"
            class="w-full text-left px-4 py-3 rounded border border-gray-200
                   text-sm hover:bg-gray-50 hover:border-gray-300 transition-colors"
          >
            {{ label }}
          </button>
        {% endfor %}
      </div>
    </div>

    <!-- フッター -->
    <div class="p-4 border-t border-gray-100">
      <button onclick="closeReportModal()"
        class="w-full py-2 text-sm text-gray-500 hover:text-gray-700">
        キャンセル
      </button>
    </div>

  </div>
</div>

<script>
  function openReportModal(targetType, targetId) {
    // hidden フィールドに値をセットする
    document.getElementById("report-target-type").value = targetType;
    document.getElementById("report-target-id").value = targetId;

    // モーダルを表示する
    document.getElementById("report-overlay").classList.remove("hidden");
    document.getElementById("report-modal").classList.remove("hidden");
  }

  function closeReportModal() {
    document.getElementById("report-overlay").classList.add("hidden");
    document.getElementById("report-modal").classList.add("hidden");

    // 報告結果をリセットする（次回開いたとき理由ボタンが表示される）
    // ページをリロードせずにリセットするため HTMX で再取得する
    htmx.ajax("GET", "/components/report-reasons", "#report-result");
  }
</script>
```

## templates/components/report_reasons.html

対応: 第7章。正本: `templates/components/report_reasons.html`

```html
<!-- templates/components/report_reasons.html -->
{% for value, label in report_reasons %}
  <button
    hx-post="/reports"
    hx-include="#report-target-type, #report-target-id"
    hx-vals='{"reason": "{{ value }}"}'
    hx-target="#report-result"
    hx-swap="innerHTML"
    class="w-full text-left px-4 py-3 rounded border border-gray-200
           text-sm hover:bg-gray-50 hover:border-gray-300 transition-colors"
  >
    {{ label }}
  </button>
{% endfor %}
```
