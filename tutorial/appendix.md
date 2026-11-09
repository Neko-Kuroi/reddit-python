# 付録　ファイル構成一覧

> コードファイルの全文は「全コード付録」に再録しています（正本から機械生成）: [1 基盤とマイグレーション](appendix_code_01_foundation.md) / [2 モデルとサービス](appendix_code_02_models_services.md) / [3 ルーターと入口](appendix_code_03_routers.md) / [4 テンプレート](appendix_code_04_templates.md)。章の中で完成形を追いにくいファイル（段階的に育てる `main.py` や `app/templating.py` など）は、こちらで完成形をそのまま確認できます。

---

## 完成時のディレクトリ構造

```
reddit_clone/
│
├─ main.py                            ← アプリの入口（第1章で作成、第5・6章で更新）
├─ requirements.txt                   ← 依存関係（第1章）
├─ .env                               ← 環境変数（第1章。各自で作成する）
├─ .gitignore                         ← 第1章
│
├─ app/
│   ├─ config.py                      ← 設定管理（第1章）
│   ├─ database.py                    ← DB 接続・セッション供給（第1章）
│   ├─ auth.py                        ← セッショントークンの発行と検証（第5章）
│   ├─ dependencies.py                ← 共通 Depends（第1章で準備、第5章で完成）
│   ├─ csrf.py                        ← CSRF トークンの発行と検証（第5章）
│   ├─ templating.py                  ← 共有テンプレート基盤とカスタムフィルター（第6章）
│   │
│   ├─ accounts/                      ← ユーザー
│   │   ├─ models.py                  ← User モデル（第3章）
│   │   ├─ schemas.py                 ← 入力スキーマ（第3章）
│   │   ├─ services.py                ← ビジネスロジック（第4章）
│   │   └─ router.py                  ← 登録・ログイン・プロフィール（第5章）
│   │
│   ├─ communities/                   ← コミュニティ
│   │   ├─ models.py                  ← Subreddit・SubredditMember モデル（第3章）
│   │   ├─ schemas.py                 ← 入力スキーマ（第3章）
│   │   ├─ services.py                ← ビジネスロジック（第4章）
│   │   └─ router.py                  ← コミュニティ画面（第6章）
│   │
│   ├─ posts/                         ← 投稿と投票
│   │   ├─ models.py                  ← Post・Vote モデル（第3章）
│   │   ├─ schemas.py                 ← 入力スキーマ（第3章）
│   │   ├─ services.py                ← ビジネスロジック（第4章）
│   │   └─ router.py                  ← 投稿・ホーム・検索（第6章）
│   │
│   ├─ comments/                      ← コメント
│   │   ├─ models.py                  ← Comment モデル（第3章）
│   │   ├─ services.py                ← ビジネスロジック（第4章）
│   │   └─ router.py                  ← コメントと報告の受け口（第6章）
│   │       ※ schemas.py はありません（入力はフォームから直接受け取ります）
│   │
│   └─ reports/                       ← 報告
│       ├─ models.py                  ← Report モデル（第3章）
│       └─ services.py                ← ビジネスロジック（第4章）
│           ※ router.py はありません（受け口は comments/router.py の POST /reports です）
│
├─ alembic/
│   ├─ env.py                         ← マイグレーションの実行環境（第1章）
│   └─ versions/                      ← マイグレーション8件（第2章）
│       ├─ XXXX_enable_uuid_extension.py
│       ├─ XXXX_create_users.py
│       ├─ XXXX_create_subreddits.py
│       ├─ XXXX_create_subreddit_members.py
│       ├─ XXXX_create_posts.py
│       ├─ XXXX_create_comments.py
│       ├─ XXXX_create_votes.py
│       └─ XXXX_create_reports.py
│
├─ templates/
│   ├─ base.html                      ← 全画面共通レイアウト（第5章）
│   ├─ 404.html                       ← 404 ページ（第5章）
│   ├─ accounts/
│   │   ├─ register.html              ← 登録（第5章）
│   │   ├─ login.html                 ← ログイン（第5章）
│   │   └─ profile.html               ← プロフィール（第7章）
│   ├─ communities/
│   │   ├─ subreddit.html             ← コミュニティページ（第6章）
│   │   └─ new_subreddit.html         ← コミュニティ作成（第6章）
│   ├─ posts/
│   │   ├─ detail.html                ← 投稿詳細（第6章）
│   │   ├─ new_post.html              ← 投稿作成（第6章）
│   │   ├─ home.html                  ← ホーム Feed（第7章）
│   │   └─ search.html                ← 検索結果（第6章）
│   └─ components/
│       ├─ join_button.html           ← Join / Leave ボタン（第6章）
│       ├─ post_list.html             ← 投稿リスト（第6章）
│       ├─ vote_buttons.html          ← 投票ボタン（第6章）
│       ├─ post_card.html             ← 投稿カード（第6章）
│       ├─ comment_tree.html          ← コメントツリー（第6章）
│       ├─ report_modal.html          ← 報告モーダル（第7章）
│       └─ report_reasons.html        ← 報告理由の再表示用（第7章）
│
└─ static/
    ├─ .gitkeep                       ← Git で空の static/ を残すための目印（第1章）
    └─ css/                           ← 本書では使いません（CSS は CDN の Tailwind を使用）
```

※ `app/` の各ディレクトリには `__init__.py` を置きません。Python 3 の namespace package の仕組みで、そのまま import できます（第1章の補足を参照）。

---

## ファイルと章の対応表

| ファイル | 実装した章 |
|---------|-----------|
| `main.py` | 第1章（初版）→ 第5章（Router 登録）→ 第6章（完成版） |
| `requirements.txt` | 第1章 |
| `.env` / `.gitignore` | 第1章 |
| `app/config.py` | 第1章 |
| `app/database.py` | 第1章（第3章で TimestampMixin を追加） |
| `app/dependencies.py` | 第1章（準備）→ 第5章（完成） |
| `alembic/env.py` | 第1章 |
| `alembic/versions/*.py`（8件） | 第2章 |
| `app/accounts/models.py` | 第3章 |
| `app/accounts/schemas.py` | 第3章 |
| `app/communities/models.py` | 第3章 |
| `app/communities/schemas.py` | 第3章 |
| `app/posts/models.py` | 第3章（Vote は 3-10 で追加） |
| `app/posts/schemas.py` | 第3章 |
| `app/comments/models.py` | 第3章 |
| `app/reports/models.py` | 第3章 |
| `app/accounts/services.py` | 第4章 |
| `app/communities/services.py` | 第4章 |
| `app/posts/services.py` | 第4章 |
| `app/comments/services.py` | 第4章 |
| `app/reports/services.py` | 第4章 |
| `app/auth.py` | 第5章 |
| `app/accounts/router.py` | 第5章 |
| `templates/base.html` | 第5章 |
| `templates/accounts/register.html` | 第5章 |
| `templates/accounts/login.html` | 第5章 |
| `templates/404.html` | 第5章 |
| `app/csrf.py` | 第5章 |
| `app/communities/router.py` | 第6章 |
| `templates/communities/subreddit.html` | 第6章 |
| `templates/communities/new_subreddit.html` | 第6章 |
| `templates/components/join_button.html` | 第6章 |
| `templates/components/post_list.html` | 第6章 |
| `app/posts/router.py` | 第6章 |
| `templates/posts/detail.html` | 第6章 |
| `templates/posts/new_post.html` | 第6章 |
| `app/comments/router.py` | 第6章（報告理由の再表示は第7章で追加） |
| `templates/components/vote_buttons.html` | 第6章 |
| `templates/components/post_card.html` | 第6章 |
| `templates/components/comment_tree.html` | 第6章 |
| `templates/posts/search.html` | 第6章 |
| `app/templating.py` | 第6章（フィルターとグローバルの追加は第7章） |
| `templates/components/report_modal.html` | 第7章 |
| `templates/components/report_reasons.html` | 第7章 |
| `templates/posts/home.html` | 第7章 |
| `templates/accounts/profile.html` | 第7章 |

### マイグレーションの revision 連鎖

適用順はファイル名ではなく、各ファイルの `revision` / `down_revision` の宣言で決まります。

| revision | ファイル | 内容 | 章 |
|----------|---------|------|----|
| `0001` | `XXXX_enable_uuid_extension.py` | UUID 拡張（uuid-ossp）を有効化 | 2-3 |
| `0002` | `XXXX_create_users.py` | users テーブル | 2-4 |
| `0003` | `XXXX_create_subreddits.py` | subreddits テーブル | 2-5 |
| `0004` | `XXXX_create_subreddit_members.py` | subreddit_members テーブル | 2-6 |
| `0005` | `XXXX_create_posts.py` | posts テーブル | 2-7 |
| `0006` | `XXXX_create_comments.py` | comments テーブル | 2-8 |
| `0007` | `XXXX_create_votes.py` | votes テーブル | 2-9 |
| `0008` | `XXXX_create_reports.py` | reports テーブル | 2-10 |

---

## URL とページの対応表

認証の見方: 「必須」は `Depends(require_auth)` で、未ログインだとログインページへリダイレクト（303）されます。「任意」は `Depends(get_current_user)` で、未ログインでも表示できます（その場合 `current_user` は空です）。状態を変える POST はすべて、CSRF トークンの検証対象です（第5章 5-9）。

| メソッド | URL | 処理（Router / ハンドラ） | 認証 | 備考 |
|---------|-----|--------------------------|------|------|
| GET | `/` | posts / `home` | 必須 | ホーム Feed |
| GET | `/register` | accounts / `register_page` | 不要 | 登録ページ |
| POST | `/register` | accounts / `register` | 不要 | 登録（成功すると自動ログイン） |
| GET | `/login` | accounts / `login_page` | 不要 | ログインページ |
| POST | `/login` | accounts / `login` | 不要 | ログイン |
| POST | `/logout` | accounts / `logout` | 不要 | ログアウト |
| GET | `/u/{username}` | accounts / `profile` | 任意 | プロフィール（存在しないユーザーは 404） |
| GET | `/subreddits/new` | communities / `new_subreddit_page` | 必須 | コミュニティ作成ページ |
| POST | `/subreddits/new` | communities / `create_subreddit` | 必須 | コミュニティ作成 |
| GET | `/r/{name}` | communities / `subreddit_page` | 任意 | コミュニティページ |
| GET | `/r/{name}/posts` | communities / `load_more_posts` | 任意 | HTMX 用（もっと見る、部分 HTML） |
| POST | `/r/{name}/join` | communities / `join_subreddit` | 必須 | HTMX 用（参加） |
| POST | `/r/{name}/leave` | communities / `leave_subreddit` | 必須 | HTMX 用（脱退） |
| GET | `/r/{name}/submit` | posts / `new_post_page` | 必須 | 投稿作成ページ（`/{post_id}` より前に定義する） |
| POST | `/r/{name}/submit` | posts / `create_post` | 必須 | 投稿作成 |
| GET | `/r/{name}/{post_id}` | posts / `post_detail` | 任意 | 投稿詳細 |
| POST | `/posts/{post_id}/vote` | posts / `vote_post` | 必須 | HTMX 用（投稿への投票） |
| POST | `/posts/{post_id}/delete` | posts / `delete_post` | 必須 | 投稿の削除 |
| GET | `/search` | posts / `search` | 任意 | 検索結果 |
| POST | `/posts/{post_id}/comments` | comments / `create_comment` | 必須 | コメント投稿（返信は `parent_id` 付き） |
| POST | `/comments/{comment_id}/vote` | comments / `vote_comment` | 必須 | HTMX 用（コメントへの投票） |
| POST | `/comments/{comment_id}/delete` | comments / `delete_comment` | 必須 | コメントの削除 |
| POST | `/reports` | comments / `create_report` | 必須 | HTMX 用（報告モーダルからの送信） |
| GET | `/components/report-reasons` | comments / `report_reasons` | 不要 | HTMX 用（報告理由ボタンの再表示、部分 HTML） |
| GET | `/health` | main.py / `health` | 不要 | ヘルスチェック（`{"status": "ok"}` を返す） |

---

## Service の関数一覧

第4章で作った Service 層の関数の一覧です。右端の列は、原典（Elixir 版）の Context 関数との対応を示します。アンダースコアで始まる関数は、その Service の内部でのみ使う補助関数です。

### Accounts（`app/accounts/services.py`）

| 関数 | 説明 | 原典 Context の対応 |
|------|------|-------------------|
| `create_user(db, data)` | ユーザーを登録する | `register_user/1` |
| `authenticate_user(db, email, password)` | メールとパスワードでユーザーを認証する | `login_user/2` |
| `get_user_by_id(db, user_id)` | id でユーザーを取得する（無ければ `None`） | `get_user!/1` に相当（ただし例外ではなく `None` を返す） |
| `get_user_by_username(db, username)` | username でユーザーを取得する（無ければ `None`） | `get_user_by_username/1` |
| `update_karma(db, user_id, karma_type, amount)` | Karma を増減する | `update_karma/3` |

### Communities（`app/communities/services.py`）

| 関数 | 説明 | 原典 Context の対応 |
|------|------|-------------------|
| `create_subreddit(db, data, owner_id)` | コミュニティを作成する（作成者の moderator 登録含む） | `create_subreddit/1` |
| `get_subreddit_by_name(db, name)` | name でコミュニティを取得する（無ければ `None`） | `get_subreddit_by_name/1` |
| `get_subreddit_by_id(db, subreddit_id)` | id でコミュニティを取得する（無ければ `None`） | `get_subreddit!/1` に相当（ただし例外ではなく `None` を返す） |
| `join_subreddit(db, user_id, subreddit_id)` | コミュニティに参加する | `join_subreddit/2` |
| `leave_subreddit(db, user_id, subreddit_id)` | コミュニティから脱退する（オーナーは脱退できない） | `leave_subreddit/2` |
| `is_member(db, user_id, subreddit_id)` | 参加済みかどうかを確認する | `member?/2` |
| `is_moderator(db, user_id, subreddit_id)` | モデレーターかどうかを確認する | `moderator?/2` |
| `list_joined_subreddits(db, user_id)` | 参加済みコミュニティ一覧を返す（サイドバー用） | `list_joined_subreddits/1` |
| `search_subreddits(db, query)` | キーワードでコミュニティを検索する | `search_subreddits/1` |

### Posts（`app/posts/services.py`）

| 関数 | 説明 | 原典 Context の対応 |
|------|------|-------------------|
| `create_post(db, data, author_id, subreddit_id)` | 投稿を作成する | `create_post/1` |
| `get_post(db, post_id)` | id で投稿を取得する（無ければ `None`） | `get_post/1` |
| `list_posts(db, subreddit_id, sort, page)` | コミュニティの投稿一覧と次ページの有無を取得する（コメント数付き） | `list_posts/3` |
| `list_home_posts(db, user_id, sort, page)` | ホーム Feed の投稿一覧と次ページの有無を取得する | `list_home_posts/3` |
| `list_user_posts(db, user_id, sort, page)` | ユーザーの投稿一覧と次ページの有無を取得する（プロフィール用） | `list_user_posts/2` |
| `search_posts(db, query)` | キーワードで投稿を検索する | `search_posts/1` |
| `vote_post(db, user_id, post_id, value)` | 投稿に投票する（4つのパターンを処理する） | `vote_post/3` |
| `delete_post(db, post_id, user_id, subreddit_id)` | 投稿を削除する | `delete_post/3` |
| `_apply_sort(query, sort)` | （内部）一覧の並び替えを適用する | — |
| `_get_vote(db, user_id, target_type, target_id)` | （内部）既存の投票を取得する | — |
| `_create_vote(db, user_id, target_type, target_id, value)` | （内部）投票を作成する | — |
| `_update_post_score(db, post, diff)` | （内部）投稿のスコアと Hot スコア、作者の Karma を更新する | — |

### Comments（`app/comments/services.py`）

| 関数 | 説明 | 原典 Context の対応 |
|------|------|-------------------|
| `create_comment(db, body, author_id, post_id, parent_id)` | コメントを作成する（親コメントの存在と、同じ投稿に属することの確認を含む） | `create_comment/1` |
| `list_comments(db, post_id)` | 投稿のコメントをツリー構造で取得する | `list_comments/1` |
| `vote_comment(db, user_id, comment_id, value)` | コメントに投票する（投稿と同じ4パターン） | `vote_comment/3` |
| `delete_comment(db, comment_id, user_id, subreddit_id)` | コメントを削除する | `delete_comment/3` |
| `_build_tree(comments)` | （内部）フラットなリストをツリー構造に変換する | — |
| `_update_comment_score(db, comment, diff)` | （内部）コメントのスコアと作者の Karma を更新する | — |

### Reports（`app/reports/services.py`）

| 関数 | 説明 | 原典 Context の対応 |
|------|------|-------------------|
| `create_report(db, reporter_id, target_type, target_id, reason)` | 投稿またはコメントを報告する | `create_report/1` |
| `_get_author_id(db, target_type, target_id)` | （内部）報告対象の作者を取得する | — |

---

## 原典にあって Python 版に無い関数

原典（Elixir 版）の Context にはあって、Python 版の Service には無い関数が3件あります。いずれも、呼び出し側の書き方を変えることで代替済みです（機能としての欠落ではありません）。

| 原典の関数 | Python 版での扱い |
|-----------|------------------|
| `change_user_registration/1`（フォーム初期化用の空のチェンジセットを返す） | ありません。登録画面の Router が、空のエラー情報などをテンプレートへ直接渡す形で代替しています |
| `get_post!/1`（無ければ例外を投げて取得する） | ありません。`get_post` が `None` を返し、Router 側が 404 に変換する形で代替しています。`get_user!/1`・`get_subreddit!/1` についても同様で、`get_user_by_id`・`get_subreddit_by_id` が `None` 返却で相当します |
| `get_comment!/1`（無ければ例外を投げて取得する） | ありません。`delete_comment` が Service の中で直接クエリして取得する形で代替しています |
