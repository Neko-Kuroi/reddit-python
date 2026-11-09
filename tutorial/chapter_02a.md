# 第2章　データベース設計とマイグレーション（前編）

---

### この章で学ぶこと

- 作るもの: 7つのテーブルのマイグレーション（前編では UUID 拡張と users・subreddits・subreddit_members・posts の4件、後編で残り3件）
- 学ぶ考え方: マイグレーション（テーブル構成の変更履歴をコードで管理する考え方）、revision の連鎖による実行順序の決まり方、主キーに UUID を使う理由、外部キーと削除時の振る舞い（ondelete）、インデックスの役割

### 前提

- 第1章が終わっていること（プロジェクトと仮想環境、`.env`、Alembic の初期設定）
- PostgreSQL が起動していて、接続できること

### 全体の中での位置

この章は **Data 層** の土台を作る章です。まず「データの保存先の形」をテーブルとして決めます。第3章では、この形を Python のクラス（SQLAlchemy モデル）として、もう一度書き表します。

なお、マイグレーション8件の全文は、巻末の全コード付録 1（appendix_code_01）に収録しています。

---

## 2-1　Alembic とは

Alembic は SQLAlchemy のマイグレーションツールです。Elixir の Ecto マイグレーションに相当します。

```
Elixir版                FastAPI版
────────────────────────────────────
mix ecto.gen.migration  alembic revision --autogenerate
mix ecto.migrate        alembic upgrade head
mix ecto.rollback       alembic downgrade -1
```

**自動生成の仕組み**

Alembic は SQLAlchemy の Models を読み取り、現在の DB の状態と比較して差分を自動的にマイグレーションファイルに書き出します。

```bash
# Models を書いてからこのコマンドを実行するだけで
# マイグレーションファイルが自動生成される
alembic revision --autogenerate -m "create users"
```

**読み解き**

マイグレーションとは、テーブル構成の変更を「1回分の変更ファイル」として積み重ね、管理する仕組みです。データベースを直接手で書き換えるのではなく、変更の履歴がコードとして残るため、誰の環境でも同じ手順で同じ構成を再現できます。問題があれば、1つ前の状態に戻す（downgrade）こともできます。各変更ファイルには、前に進める処理（`upgrade`）と戻す処理（`downgrade`）の両方を書きます。

なお、本書ではモデル（第3章）を後で作る都合上、第2章のマイグレーションは自動生成ではなく **手で書きます**。上の自動生成の例は、モデルが先にある場合の仕組みの紹介です。この章の時点では実行しません。

---

## 2-2　テーブル設計

Elixir版と全く同じ7つのテーブルを使います。

| テーブル | 役割 |
|---------|------|
| `users` | ユーザーアカウント・Karma |
| `subreddits` | コミュニティ |
| `subreddit_members` | ユーザーとコミュニティの参加関係 |
| `posts` | 投稿（テキスト・リンク） |
| `comments` | コメント・返信 |
| `votes` | 投票（投稿とコメント両方に対応） |
| `reports` | 報告 |

依存関係の順番も同じです。

```
① users              ← すべての土台
② subreddits         ← users に依存
③ subreddit_members  ← users + subreddits に依存
④ posts              ← users + subreddits に依存
⑤ comments          ← users + posts に依存（自己参照あり）
⑥ votes             ← users に依存
⑦ reports           ← users に依存
```

---

## 2-3　UUID の設定

Elixir版と同様に主キーは UUID を使います。PostgreSQL の `uuid-ossp` 拡張を有効にします。

最初のマイグレーションファイルを手動で作成します。

```bash
alembic revision -m "enable uuid extension"
```

生成されたファイルを編集します。各マイグレーションファイルの先頭には `revision`（そのファイル自身の ID）と `down_revision`（1つ前のファイルの ID）の宣言を書きます。Alembic はこの連鎖をたどって実行順序を決めるため、宣言が無いファイルがあると `alembic upgrade head` が失敗します。本書では第2章の作成順に `0001` から `0008` まで連鎖させます（ファイル名の `XXXX_` は生成日時などに置き換わる部分で、順序はファイル名ではなくこの宣言で決まります）。

```python
# alembic/versions/XXXX_enable_uuid_extension.py
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

def downgrade() -> None:
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
```

**読み解き**

実行順序の決め方が、この節の要点です。Alembic はファイル名ではなく、`revision`（そのファイル自身の ID）と `down_revision`（直前のファイルの ID）の連鎖をたどって順番を決めます。鎖の始まりは `down_revision = None` のファイル（ここでは `0001`）です。宣言が欠けたファイルがあると、Alembic は順序を特定できずにエラーで止まります（実際に起きやすい失敗なので、第8章の「よくあるエラー」にも載せています）。

主キー（テーブル内で行を1つに特定する列）に UUID を使うのは、連番（1、2、3…）と違って、ID から登録件数や新しさが推測できないことと、複数箇所で同時に作っても衝突しにくいことが理由です。生成は DB 側の `uuid_generate_v4()` に任せるため、最初に拡張を有効化しておきます。

---

## 2-4　users テーブル

```bash
alembic revision --autogenerate -m "create users"
```

```python
# alembic/versions/XXXX_create_users.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("username", sa.String(20), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("post_karma", sa.Integer(), server_default="0", nullable=False),
        sa.Column("comment_karma", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
```

**読み解き**

`server_default=sa.text("uuid_generate_v4()")` は DB 側で UUID を自動生成します。Python 側で UUID を生成することもできますが、DB 側で生成する方が確実です。なお `sa.text(...)` は「これは SQL の式である」という印です。ただの文字列として書くと、SQL 側では文字列そのものとして解釈されてしまい、既定値として機能しません（第3章のモデル側でも同じ注意が出てきます）。

`server_default="0"` は DB レベルのデフォルト値です。アプリから値を指定しなかった場合に自動的に `0` が入ります。

`username` と `email` に付けたユニークインデックス（`unique=True` の `create_index`）は、「同じユーザー名・同じメールアドレスは2つ登録できない」という決まりを、アプリ側の確認ではなく DB 自身に守らせるためのものです。アプリの確認だけでは、同時に2つの登録が来た場合にすり抜けることがあります。

---

## 2-5　subreddits テーブル

```python
# alembic/versions/XXXX_create_subreddits.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "subreddits",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("name", sa.String(21), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_subreddits_name", "subreddits", ["name"], unique=True)
    op.create_index("ix_subreddits_owner_id", "subreddits", ["owner_id"])

def downgrade() -> None:
    op.drop_index("ix_subreddits_owner_id", table_name="subreddits")
    op.drop_index("ix_subreddits_name", table_name="subreddits")
    op.drop_table("subreddits")
```

**読み解き**

`owner_id` の `ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT")` が、外部キーという仕組みです。「この列には、users テーブルに実在する id しか入れられない」という制約を DB が守ります。`ondelete` は、参照先（ここでは所有者であるユーザー）が消えたときの振る舞いです。`RESTRICT` は「参照している行があるうちは消せない」という意味で、コミュニティの所有者がいなくなる事態を防ぐための選択です。次の 2-6 では逆に「親が消えたら一緒に消える」`CASCADE` が出てきます。どちらを選ぶかは、そのデータが親なしでも意味を持つかどうかで決めます。

---

## 2-6　subreddit_members テーブル

```python
# alembic/versions/XXXX_create_subreddit_members.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "subreddit_members",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("subreddit_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(20), server_default="member", nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subreddit_id"], ["subreddits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    # 1人1回のみ Join 可能
    op.create_index("ix_subreddit_members_unique",
                    "subreddit_members", ["user_id", "subreddit_id"], unique=True)
    op.create_index("ix_subreddit_members_user_id",
                    "subreddit_members", ["user_id"])
    op.create_index("ix_subreddit_members_subreddit_id",
                    "subreddit_members", ["subreddit_id"])

def downgrade() -> None:
    op.drop_index("ix_subreddit_members_subreddit_id", table_name="subreddit_members")
    op.drop_index("ix_subreddit_members_user_id", table_name="subreddit_members")
    op.drop_index("ix_subreddit_members_unique", table_name="subreddit_members")
    op.drop_table("subreddit_members")
```

**読み解き**

`subreddit_members` は、ユーザーとコミュニティの「参加」という関係そのものを表す中間テーブルです。関係を独立したテーブルにすることで、参加した日時（`inserted_at`）や役割（`role`。作成者は `moderator`、参加者は `member`）のような、関係に付随する情報を持てます。

`(user_id, subreddit_id)` の組み合わせに付けたユニークインデックスが、「同じコミュニティへの二重参加」を DB に防がせる仕掛けです。外部キーの `ondelete="CASCADE"` は、ユーザーやコミュニティが削除されたら参加記録も一緒に消すという選択です（参加記録は単独では意味を持たないため）。

---

## 2-7　posts テーブル

```python
# alembic/versions/XXXX_create_posts.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),       # "text" | "link"
        sa.Column("body", sa.Text(), nullable=True),            # type=text のみ
        sa.Column("url", sa.String(2048), nullable=True),       # type=link のみ
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hot_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("subreddit_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subreddit_id"], ["subreddits.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_posts_author_id", "posts", ["author_id"])
    op.create_index("ix_posts_subreddit_id", "posts", ["subreddit_id"])
    # Hot Feed 用の複合インデックス
    op.create_index("ix_posts_subreddit_hot",
                    "posts", ["subreddit_id", "hot_score"])
    # New Feed 用の複合インデックス
    op.create_index("ix_posts_subreddit_new",
                    "posts", ["subreddit_id", "inserted_at"])
    # ホーム Feed 用
    op.create_index("ix_posts_hot_score", "posts", ["hot_score"])

def downgrade() -> None:
    op.drop_index("ix_posts_hot_score", table_name="posts")
    op.drop_index("ix_posts_subreddit_new", table_name="posts")
    op.drop_index("ix_posts_subreddit_hot", table_name="posts")
    op.drop_index("ix_posts_subreddit_id", table_name="posts")
    op.drop_index("ix_posts_author_id", table_name="posts")
    op.drop_table("posts")
```

**読み解き**

posts には、単独の列へのインデックスに加えて、複合インデックス（複数の列を組み合わせたインデックス）が3つあります。たとえば `ix_posts_subreddit_hot` は `(subreddit_id, hot_score)` の組で、「あるコミュニティの投稿を Hot スコア順に並べる」という、このアプリで最も多い読み方を速くするためのものです。インデックスは本の索引と同じで、探すのは速くなりますが、書き込みのたびに索引側も更新されるため、無制限には増やしません。

外部キーの `ondelete` は、相手によって選んでいます。`author_id` 側は `RESTRICT`（投稿のあるユーザーは消せない）、`subreddit_id` 側は `CASCADE`（コミュニティが消えたら投稿も消える）です。

---

後編では `comments`・`votes`・`reports` テーブルとマイグレーションの実行方法を説明します。
