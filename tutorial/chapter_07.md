# 第7章　HTMX の詳細と報告モーダル

---

### この章で学ぶこと

- 作るもの: 報告モーダル（`components/report_modal.html`）と理由ボタンのリセット用部品・ホーム Feed とプロフィールのテンプレート、`app/templating.py` への `format_karma` フィルターと報告理由グローバルの追加
- 学ぶ考え方: HTMX の `hx-include` と `name` 属性、部品とスクリプトの置き場所の設計、状態をどこに置くか（画面側かサーバー側か）

### 前提

- 第6章までが終わっていること（Router と主要テンプレートがそろい、ホームとプロフィールだけが未表示の状態）

### 全体の中での位置

この章で画面まわりが完成します。第6章で残っていたホームとプロフィールのテンプレートを作り、報告モーダルという「画面をまたぐ部品」を置くことで、アプリの全ページが表示できるようになります。

なお、この章で作るテンプレートの全文は全コード付録 4（appendix_code_04）に、`app/templating.py` の完成形（この章の追加分を含む）は全コード付録 1（appendix_code_01）に収録しています。

---

## 7-1　HTMX の主要属性まとめ

第6章で使った HTMX の属性を整理します。

```
属性              説明
──────────────────────────────────────────────────────
hx-get            GET リクエストを送る
hx-post           POST リクエストを送る
hx-put            PUT リクエストを送る
hx-delete         DELETE リクエストを送る

hx-target         レスポンスを入れる要素（CSS セレクタ）
hx-swap           差し替え方法
  innerHTML         要素の中身を差し替える（デフォルト）
  outerHTML         要素ごと差し替える
  beforeend         要素の末尾に追加する
  afterend          要素の後ろに追加する

hx-trigger        発火タイミング
  click             クリック（デフォルト）
  revealed          要素がスクロールで表示されたとき
  submit            フォーム送信
  change            値が変わったとき

hx-vals           追加で送るパラメータ（JSON形式）
hx-include        追加で含めるフォームフィールド
hx-indicator      リクエスト中に表示するローディング要素
hx-confirm        実行前に確認ダイアログを表示する
```

---

## 7-2　HTMX と通常リクエストの使い分け

このアプリでの使い分けは以下の通りです。

```
通常のフォーム POST（ページ全体が切り替わる）
  ├─ ログイン・ログアウト
  ├─ 投稿作成
  ├─ コメント投稿
  └─ Subreddit 作成

HTMX（部分的に更新する）
  ├─ 投票（スコアだけ更新）
  ├─ Join / Leave（ボタンだけ更新）
  ├─ 無限スクロール（投稿リストに追記）
  └─ 報告モーダル（モーダルの表示・非表示）
```

---

## 7-3　報告モーダルの実装

報告モーダルは JavaScript と HTMX を組み合わせて実装します。

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

**読み解き**

`hx-include="#report-target-type, #report-target-id"` は指定した要素の値をリクエストに含めます。

```html
<!-- この2つの hidden フィールドが POST のボディに含まれる -->
<input type="hidden" id="report-target-type" name="target_type" value="post" />
<input type="hidden" id="report-target-id" name="target_id" value="abc-123" />
```

報告ボタンを押したとき、`target_type` と `target_id` が一緒に送られます。

hidden フィールドには **`name` 属性が必須**です。`hx-include`（および通常のフォーム送信）は、値を `name` をキーにして集めます。`id` だけでは送信データに含まれず、サーバー側で `target_id` が受け取れません。`id` は JavaScript が要素を見つけるための目印、`name` は送信データのキー、と役割が分かれている点に注意してください。

モーダルの置き場所についても確認しておきます。このモーダルは「報告ボタンのあるページすべて」に include する約束で、開閉の関数（`openReportModal` / `closeReportModal`）もモーダル自身のテンプレートの中に置かれています。include すれば、見た目とスクリプトが一緒についてきます。第6章の `toggleReplyForm` を base.html に置いたのと対照的ですが、基準は同じで、「その部品と常に一緒に動くものは部品側に、ページを問わず使うものは共通の場所に」置きます。

「どの投稿への報告か」という状態の置き場所も、このモーダルの特徴です。状態はサーバーには無く、画面側の hidden フィールドの値として保持されます。報告ボタンが押されるたびに JavaScript が値を書き換え、理由が選ばれた時点で初めてサーバーへ送られます。画面を離れれば消えてよい情報なので、サーバー側に持たせない設計です。なお、報告の POST に個別の CSRF hidden フィールドが無いのは、第5章 5-9 の仕組みで、HTMX のリクエストには `body` の `hx-headers` 経由でトークンが自動的に付くためです。

---

## 7-4　報告理由のリセット用エンドポイント

モーダルを閉じたとき、報告ボタンをリセットするためのエンドポイントを追加します。

```python
# app/comments/router.py に追加

@router.get("/components/report-reasons", response_class=HTMLResponse)
async def report_reasons(request: Request):
    """報告モーダルの理由ボタンをリセットする"""
    return templates.TemplateResponse(
        "components/report_reasons.html",
        {"request": request}
    )
```

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

**報告理由のデータの置き場所**

モーダルと理由ボタン一覧は、どちらも `report_reasons`（値と表示ラベルのペア） をループして描画します。このデータはテンプレートに直書きせず、共有モジュール `app/templating.py` から Jinja2 のグローバルとして渡します。値の正本は第4章の Reports Service の `VALID_REASONS` 1箇所だけにし、モデルやテンプレートに複製しません。

```python
# app/templating.py に追加（第7章）
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

`format_karma` フィルターも同じ場所に追加します（7-7 で使います）。

---

## 7-5　ホーム Feed テンプレート

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

---

## 7-6　プロフィールテンプレート

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

---

## 7-7　format_karma カスタムフィルターを追加

`format_karma` フィルターは 7-4 で `app/templating.py` に追加済みです（カスタムフィルターの登録先は 6-15 の共有モジュールに統一します。main.py に登録しても描画には届きません）。

プロフィール画面（7-6）で `{{ profile_user.karma | format_karma }}` の形で使い、1000 以上の Karma を `1.2k` のような表記にします。

---

## 動作確認（この章の仕上げ）

前提: サーバーが起動していて、ログインできること。ブラウザで順に確かめます。

- [ ] ホーム（`/`）が表示され、参加中のコミュニティと投稿一覧が出る。Hot / New のタブで並び順が切り替わる
- [ ] プロフィール（`/u/{自分のユーザー名}`）が表示され、Post Karma / Comment Karma が出る
- [ ] 他人の投稿の「報告」ボタンを押すとモーダルが開き、理由を選ぶと「報告しました。ご協力ありがとうございます。」と表示される
- [ ] モーダルを閉じて、別の投稿の報告ボタンを押すと、理由ボタンが元の並びで表示される（リセットが働いている）
- [ ] 自分の投稿・コメントには報告ボタンが出ない
- [ ] 報告がデータベースに記録されている（例: psql で `SELECT target_type, reason FROM reports;` を実行し、選んだ理由の行が1件ある）
- [ ] 第6章まで `TemplateNotFound` だったホームとプロフィールの2ページが、どちらも表示できるようになった

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| 報告すると 422 になり、サーバーで `target_id` が受け取れない | hidden フィールドに `name` 属性が無い。`hx-include` は `name` をキーに値を集めるため、`id` だけでは送られない | `name="target_type"` / `name="target_id"` を付ける（7-3） |
| 報告ボタンを押してもモーダルが開かない（`openReportModal` が未定義） | そのページに `report_modal.html` が include されていない | 報告ボタンのあるページすべてに include する（7-3） |
| 2回目にモーダルを開くと、前回の「報告しました」の表示のままになっている | モーダルを閉じる際のリセットが行われていない | `closeReportModal` で `/components/report-reasons` を再取得し、`#report-result` を出し直す（7-4） |
| プロフィール表示で `No filter named 'format_karma'` になる | フィルターが共有モジュールに登録されていない | `app/templating.py` に登録する（6-15・7-4） |
| 報告の POST が 403 になる | CSRF トークンが HTMX リクエストに付いていない（base.html の meta タグや `hx-headers` が無い、またはトークンの Cookie が無い） | 第5章 5-9 の仕組みを確認する |

---

## 確認問題

1. `hx-include` が hidden フィールドの値を集める際、キーになるのは `id` と `name` のどちらですか。`id` だけだと何が起きますか。
2. 報告モーダルの「どの投稿への報告か」という状態は、どこに置かれていますか。サーバー側に置かないのはなぜですか。
3. `toggleReplyForm` は base.html に、`openReportModal` はモーダル自身のテンプレートに置かれています。この置き場所の違いは、どういう基準で決まっていますか。
4. モーダルを閉じたときに `/components/report-reasons` へ GET するのはなぜですか。ページ全体を再読み込みする方法と比べて、何が違いますか。
5. 報告理由の「値」の正本はどこにありますか。`app/templating.py` が持っているのは何ですか。

---

## まとめと次章へのつながり

この章では以下を完了しました。

```
✅ HTMX の主要属性を整理した
✅ 通常リクエストと HTMX の使い分けを明確にした
✅ 報告モーダルを実装した
✅ hx-include で hidden フィールドを活用した
✅ ホーム Feed テンプレートを実装した
✅ プロフィールテンプレートを実装した
✅ format_karma カスタムフィルターを追加した
```

次の章では動作確認と仕上げを行います。ここまでの部品がそろった状態で、起動から一通りの操作までを通しで確認し、よくあるエラーの対処を整理します。

---

## 確認問題の答え

1. `name` です。`id` は JavaScript が要素を特定するための目印で、送信データには含まれません。`id` だけだと `target_type` と `target_id` が送られず、サーバー側で必須のフォーム項目が欠けるため 422 になります。
2. 画面側です。具体的には、モーダル内の hidden フィールドの値として保持され、報告ボタンが押されるたびに JavaScript が書き換えます。「今開いているモーダルについての情報」は画面を離れれば不要で、サーバーに持つと複数のタブや「戻る」操作で実態と食い違いやすくなります。サーバーが受け取るのは、理由が選ばれた時点の報告データだけです。
3. 使う範囲の広さです。`toggleReplyForm` はコメントのある全ページで使う共通機能なので base.html に1つ置きます。`openReportModal` / `closeReportModal` はモーダルという部品と常に一緒に動くため、部品のテンプレートに同梱し、include すれば関数も一緒についてくる形にします。
4. 報告後は `#report-result` の中身が「報告しました」の表示に差し替わっているため、次に開いたとき理由ボタンを出し直す必要があるからです。部分だけを再取得すれば、ページ全体の状態（スクロール位置など）を壊さずに、モーダルだけを初期状態へ戻せます。
5. 正本は第4章の Reports Service の `VALID_REASONS` です。`app/templating.py` が持つのは、値と表示ラベルの対応（`REPORT_REASON_LABELS`）と、それを全テンプレートから使えるグローバルとして組み立てる処理だけです。値そのものを複製していないため、理由の追加・変更は正本側を直せば済みます。
