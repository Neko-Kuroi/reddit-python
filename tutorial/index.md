# Reddit クローン（Python / FastAPI 版）— ファイルインデックス

---

## チュートリアル

| ファイル | 内容 |
|---------|------|
| [第0章 はじめに](chapter_00.md) | このチュートリアルで作るもの・仕様・環境・設計思想 |
| [第1章 プロジェクトのセットアップ](chapter_01.md) | ディレクトリ作成・依存関係・DB設定・Alembic 初期設定 |
| [第2章 データベース設計とマイグレーション（前編）](chapter_02a.md) | Alembic の考え方・テーブル設計・users〜posts マイグレーション |
| [第2章 データベース設計とマイグレーション（後編）](chapter_02b.md) | comments〜reports マイグレーション・実行と確認 |
| [第3章 SQLAlchemy Models（前編）](chapter_03a.md) | SQLAlchemy とは・User・Subreddit のモデルとスキーマ |
| [第3章 SQLAlchemy Models（後編）](chapter_03b.md) | Post・Comment・Vote・Report モデル |
| [第4章 ビジネスロジック（前編）](chapter_04a.md) | Service 層の考え方・Accounts・Communities Service |
| [第4章 ビジネスロジック（中編）](chapter_04b.md) | Posts Service・投票ロジック詳細 |
| [第4章 ビジネスロジック（後編）](chapter_04c.md) | Comments・ツリーの組み立て・Reports Service |
| [第5章 認証（前編）](chapter_05a.md) | Cookie セッションの仕組み・認証ヘルパー・Depends・認証 Router |
| [第5章 認証（後編）](chapter_05b.md) | ベース・登録・ログインのテンプレート・Router 登録・CSRF 対策 |
| [第6章 画面実装（前編）](chapter_06a.md) | Communities Router・コミュニティ画面のテンプレート |
| [第6章 画面実装（中編）](chapter_06b.md) | Posts Router・投稿詳細と投稿作成のテンプレート |
| [第6章 画面実装（後編）](chapter_06c.md) | Comments Router・コンポーネント・検索・main.py 完成版 |
| [第7章 HTMX の詳細と報告モーダル](chapter_07.md) | HTMX の属性と使い分け・報告モーダル・ホームとプロフィールのテンプレート |
| [第8章 仕上げ](chapter_08.md) | ナビゲーションバーの確認・動作確認・よくあるエラー |
| [付録](appendix.md) | ファイル構成一覧・URL 対応表・Service 関数一覧 |

---

## 全コード付録（自動生成）

正本のコードファイルの全文を、Markdown の本文側にも収録したものです。正本から機械生成しています（手写しではありません）。数え方については末尾の「合計」の注記を見てください。

| ファイル | 内容 |
|---------|------|
| [全コード付録 1 基盤とマイグレーション](appendix_code_01_foundation.md) | main.py・app 直下の共通部品6件・alembic/env.py・マイグレーション8件・設定3件の全文（第1・2・5・6章） |
| [全コード付録 2 モデルとサービス](appendix_code_02_models_services.md) | モデル・スキーマ8件とサービス5件の全文（第3・4章） |
| [全コード付録 3 ルーターと入口](appendix_code_03_routers.md) | Router 4件の全文（第5〜7章） |
| [全コード付録 4 テンプレート](appendix_code_04_templates.md) | テンプレート18件の全文（第5〜7章） |

---

## コード — Python（入口と共通部品）

| ファイル | 役割 |
|---------|------|
| [main.py](../main.py) | アプリの入口（Router 登録・CSRF ミドルウェア・`/health`） |
| [app/config.py](../app/config.py) | 設定管理（環境変数） |
| [app/database.py](../app/database.py) | DB エンジンとセッション供給 |
| [app/auth.py](../app/auth.py) | セッショントークンの発行と検証 |
| [app/dependencies.py](../app/dependencies.py) | 共通 Depends（`get_current_user` / `require_auth`） |
| [app/csrf.py](../app/csrf.py) | CSRF トークンの発行と検証 |
| [app/templating.py](../app/templating.py) | 共有テンプレート基盤とカスタムフィルター |

---

## コード — Python（機能別パッケージ）

| ファイル | 内容 |
|---------|------|
| [app/accounts/models.py](../app/accounts/models.py) | User モデル |
| [app/accounts/schemas.py](../app/accounts/schemas.py) | ユーザーの入力スキーマ |
| [app/accounts/services.py](../app/accounts/services.py) | Accounts Service |
| [app/accounts/router.py](../app/accounts/router.py) | 登録・ログイン・ログアウト・プロフィール |
| [app/communities/models.py](../app/communities/models.py) | Subreddit・SubredditMember モデル |
| [app/communities/schemas.py](../app/communities/schemas.py) | コミュニティの入力スキーマ |
| [app/communities/services.py](../app/communities/services.py) | Communities Service |
| [app/communities/router.py](../app/communities/router.py) | コミュニティ画面・参加と脱退 |
| [app/posts/models.py](../app/posts/models.py) | Post・Vote モデル |
| [app/posts/schemas.py](../app/posts/schemas.py) | 投稿の入力スキーマ |
| [app/posts/services.py](../app/posts/services.py) | Posts Service |
| [app/posts/router.py](../app/posts/router.py) | 投稿・ホーム Feed・検索 |
| [app/comments/models.py](../app/comments/models.py) | Comment モデル |
| [app/comments/services.py](../app/comments/services.py) | Comments Service |
| [app/comments/router.py](../app/comments/router.py) | コメント・報告の受け口 |
| [app/reports/models.py](../app/reports/models.py) | Report モデル |
| [app/reports/services.py](../app/reports/services.py) | Reports Service |

※ `app/comments/` に schemas.py、`app/reports/` に router.py はありません（付録のディレクトリ構造を参照）。

---

## コード — Alembic（マイグレーション）

| ファイル | 内容 |
|---------|------|
| [alembic/env.py](../alembic/env.py) | マイグレーションの実行環境 |
| [alembic/versions/XXXX_enable_uuid_extension.py](../alembic/versions/XXXX_enable_uuid_extension.py) | revision `0001` — UUID 拡張の有効化 |
| [alembic/versions/XXXX_create_users.py](../alembic/versions/XXXX_create_users.py) | revision `0002` — users テーブル |
| [alembic/versions/XXXX_create_subreddits.py](../alembic/versions/XXXX_create_subreddits.py) | revision `0003` — subreddits テーブル |
| [alembic/versions/XXXX_create_subreddit_members.py](../alembic/versions/XXXX_create_subreddit_members.py) | revision `0004` — subreddit_members テーブル |
| [alembic/versions/XXXX_create_posts.py](../alembic/versions/XXXX_create_posts.py) | revision `0005` — posts テーブル |
| [alembic/versions/XXXX_create_comments.py](../alembic/versions/XXXX_create_comments.py) | revision `0006` — comments テーブル |
| [alembic/versions/XXXX_create_votes.py](../alembic/versions/XXXX_create_votes.py) | revision `0007` — votes テーブル |
| [alembic/versions/XXXX_create_reports.py](../alembic/versions/XXXX_create_reports.py) | revision `0008` — reports テーブル |

---

## コード — テンプレート

| ファイル | 内容 |
|---------|------|
| [templates/base.html](../templates/base.html) | 全画面共通レイアウト（ナビゲーションバー） |
| [templates/404.html](../templates/404.html) | 404 ページ |
| [templates/accounts/register.html](../templates/accounts/register.html) | 登録ページ |
| [templates/accounts/login.html](../templates/accounts/login.html) | ログインページ |
| [templates/accounts/profile.html](../templates/accounts/profile.html) | プロフィールページ |
| [templates/communities/subreddit.html](../templates/communities/subreddit.html) | コミュニティページ |
| [templates/communities/new_subreddit.html](../templates/communities/new_subreddit.html) | コミュニティ作成ページ |
| [templates/posts/detail.html](../templates/posts/detail.html) | 投稿詳細ページ |
| [templates/posts/new_post.html](../templates/posts/new_post.html) | 投稿作成ページ |
| [templates/posts/home.html](../templates/posts/home.html) | ホーム Feed |
| [templates/posts/search.html](../templates/posts/search.html) | 検索結果ページ |
| [templates/components/join_button.html](../templates/components/join_button.html) | Join / Leave ボタン |
| [templates/components/post_list.html](../templates/components/post_list.html) | 投稿リスト |
| [templates/components/vote_buttons.html](../templates/components/vote_buttons.html) | 投票ボタン |
| [templates/components/post_card.html](../templates/components/post_card.html) | 投稿カード |
| [templates/components/comment_tree.html](../templates/components/comment_tree.html) | コメントツリー |
| [templates/components/report_modal.html](../templates/components/report_modal.html) | 報告モーダル |
| [templates/components/report_reasons.html](../templates/components/report_reasons.html) | 報告理由の再表示用 |

---

## 合計

```
チュートリアル  17ファイル
Python コード   24ファイル
Alembic          9ファイル
テンプレート    18ファイル
─────────────────────────
合計            68ファイル
```

※ 上の内訳68ファイルに、この index.md 自身と、設定ファイル3件（`requirements.txt`・`.env`・`.gitignore`）を加えると、全72ファイルになります。
※ 全コード付録の4ファイル（appendix_code_01〜04）は、上のコード54ファイルの「再録」です。二重に数えることを避けるため、上の内訳には含めていません。ファイルの実数としては、tutorial フォルダにこの4ファイルが加わり、全76ファイル（72＋4）になります。
※ `static/.gitkeep` は、Git で空の `static/` を残すための目印ファイルです。アプリ本体や教材のファイルではないため、上のファイル数には含めていません。`static/css/` も空のディレクトリのため数えていません（CSS は CDN の Tailwind を使います）。
※ `__pycache__/` などの実行時生成物は数えていません。
