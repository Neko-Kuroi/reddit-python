# 第2章　データベース設計とマイグレーション（後編）

---

## 2-8　comments テーブル

```python
# alembic/versions/XXXX_create_comments.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "comments",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),   # 自己参照（nullable）
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_comments_post_id", "comments", ["post_id"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_author_id", "comments", ["author_id"])

def downgrade() -> None:
    op.drop_index("ix_comments_author_id", table_name="comments")
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_post_id", table_name="comments")
    op.drop_table("comments")
```

**読み解き**

`parent_id` は `comments` テーブル自身を参照しています（自己参照）。`nullable=True` にすることでトップレベルのコメント（`parent_id` が `None`）を表現します。

`ondelete="CASCADE"` は親コメントが削除されたとき、その返信も全て削除します。

---

## 2-9　votes テーブル

```python
# alembic/versions/XXXX_create_votes.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),          # +1 | -1
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),   # "post" | "comment"
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    # 1人1票の制約
    op.create_index("ix_votes_unique",
                    "votes", ["user_id", "target_type", "target_id"], unique=True)
    op.create_index("ix_votes_target",
                    "votes", ["target_type", "target_id"])

def downgrade() -> None:
    op.drop_index("ix_votes_target", table_name="votes")
    op.drop_index("ix_votes_unique", table_name="votes")
    op.drop_table("votes")
```

**読み解き**

votes は「投稿への投票」と「コメントへの投票」を、1つのテーブルで扱います。対象は `target_type`（`"post"` か `"comment"`）と `target_id` の組で表すため、対象側への外部キーは張れません（どちらのテーブルを指すかが行ごとに変わるためです）。その代わり、`(user_id, target_type, target_id)` のユニークインデックスで、「1人が同じ対象に2票入れられない」ことを DB に守らせます。この「型＋IDで対象を指す」設計は、第3章のモデルのアソシエーションの書き方にも影響します（3-7 の `votes` の特殊な書き方を参照）。

---

## 2-10　reports テーブル

```python
# alembic/versions/XXXX_create_reports.py
import sqlalchemy as sa
from alembic import op

# Alembic がマイグレーションの順序を特定するための宣言
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), server_default=sa.text("uuid_generate_v4()"),
                  nullable=False),
        sa.Column("reason", sa.String(50), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("target_type", sa.String(10), nullable=False),  # "post" | "comment"
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("inserted_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reporter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id")
    )
    op.create_index("ix_reports_target",
                    "reports", ["target_type", "target_id"])
    op.create_index("ix_reports_reporter_id",
                    "reports", ["reporter_id"])

def downgrade() -> None:
    op.drop_index("ix_reports_reporter_id", table_name="reports")
    op.drop_index("ix_reports_target", table_name="reports")
    op.drop_table("reports")
```

**読み解き**

reports も votes と同じく、対象を `target_type` と `target_id` の組で表します（対象側への外部キーが無いのは、votes と同じ理由です）。報告した人（`reporter_id`）には外部キーを張り、`CASCADE` で、ユーザーが削除されたら報告も一緒に消えるようにしています。

---

## 2-11　マイグレーションを実行する

DB を作成してからマイグレーションを実行します。

```bash
# DB を作成する（psql で手動作成）
psql -U postgres -c "CREATE DATABASE reddit_clone_dev;"

# 全マイグレーションを実行する
alembic upgrade head
```

成功すると以下のように表示されます。

```
INFO  [alembic.runtime.migration] Running upgrade  -> 0001, enable uuid extension
INFO  [alembic.runtime.migration] Running upgrade 0001 -> 0002, create users
INFO  [alembic.runtime.migration] Running upgrade 0002 -> 0003, create subreddits
...（続く）
INFO  [alembic.runtime.migration] Running upgrade 0007 -> 0008, create reports
```

---

## 2-12　マイグレーションのやり直し方

```bash
# 1つ前に戻す
alembic downgrade -1

# 全てリセット
alembic downgrade base

# 現在の状態を確認する
alembic current

# 履歴を確認する
alembic history
```

---

## 2-13　テーブルの確認

```bash
psql -d reddit_clone_dev

# テーブル一覧
\dt

# posts テーブルの構造
\d posts
```

以下のように表示されれば成功です。

```
           List of relations
 Schema |        Name         | Type  |  Owner
--------+---------------------+-------+----------
 public | alembic_version     | table | postgres
 public | comments            | table | postgres
 public | posts               | table | postgres
 public | reports             | table | postgres
 public | subreddit_members   | table | postgres
 public | subreddits          | table | postgres
 public | users               | table | postgres
 public | votes               | table | postgres
```

`alembic_version` は Alembic が自動的に作るテーブルで、どのマイグレーションが実行済みかを記録しています。Elixir版の `schema_migrations` に相当します。

---

## 動作確認（この章の仕上げ）

2-11〜2-13 の確認に加えて、この章の終わりに次を確かめてください。前提は、PostgreSQL が起動していることと、第1章の `.env` が設定済みであることです。

- [ ] `alembic upgrade head` が 0001 から 0008 まで順に適用され、エラーなく終わる
- [ ] `alembic current` が `0008 (head)` と表示される
- [ ] `psql` の `\dt` で、7つのテーブルと `alembic_version` が並ぶ
- [ ] `alembic downgrade base` で全て戻り、もう一度 `alembic upgrade head` で戻せる（往復できること）

---

## よくあるエラーと対処

| 症状 | 原因 | 直し方 |
|------|------|--------|
| `alembic upgrade head` が revision を特定できないという趣旨のエラーで止まる | マイグレーションファイルに `revision` / `down_revision` の宣言が無い、または連鎖が切れている | 2-3 の宣言が8件すべてにあり、`0001`（down が `None`）から `0008` まで一本につながっているか確認する |
| 接続エラーでマイグレーションが始まらない | PostgreSQL が起動していない、対象 DB が無い、または `.env` の接続情報が違う | PostgreSQL の起動と、2-11 の DB 作成を確認する。接続情報は第1章 1-3 の `.env` が正本 |
| 外部キー制約のエラーで `upgrade` が途中で止まる | 適用順が依存関係と逆になっている（例: posts が users より先） | revision の連鎖が、2-2 の依存順（users → subreddits → …）と一致しているか確認する |
| `downgrade` したのにテーブルや拡張が残る | `downgrade` の内容が `upgrade` の逆になっていない | 各ファイルの `downgrade` が、作ったものを逆順に消しているか確認する |

---

## 確認問題

1. Alembic がマイグレーションの実行順序を決める手がかりは、ファイル名ですか、それとも別の何かですか。
2. `ondelete="RESTRICT"` と `ondelete="CASCADE"` の違いを、subreddits の `owner_id` と subreddit_members の外部キーを例に説明してください。
3. posts の複合インデックス `ix_posts_subreddit_hot` は、どのような読み方を速くするためのものですか。
4. users の `username` の重複を、アプリ側の確認ではなく DB のユニークインデックスに防がせるのはなぜですか。

---

## まとめと次章へのつながり

この章では以下を完了しました。

```
✅ Alembic の仕組みを理解した
✅ UUID 拡張を有効にした
✅ 7つのテーブルのマイグレーションを実装した
✅ マイグレーションを実行した
```

**Elixir版との重要な違い**

```
Elixir版
  mix ecto.gen.migration でファイルを生成
  内容を手動で書く

FastAPI版
  alembic revision --autogenerate で
  Models から自動生成できる
  ただし今回は Models を後で作るので
  手動で書いた
```

次の章では、これらのテーブルを Python のクラスとして扱うための **SQLAlchemy Models** を実装します。この章で決めた列の形（型・制約・既定値）が、そのままモデルの定義のもとになります。

---

## 確認問題の答え

1. ファイル名ではありません。各ファイル先頭の `revision`（自分の ID）と `down_revision`（直前の ID）の連鎖です。`down_revision = None` のファイルが先頭になります。
2. `RESTRICT` は「参照している行があるうちは、参照先を消せない」、`CASCADE` は「参照先が消えたら、参照している行も一緒に消える」です。コミュニティの所有者がいなくなると困るので `owner_id` は `RESTRICT`、参加記録はユーザーやコミュニティなしでは意味を持たないので `CASCADE` を選んでいます。
3. 「あるコミュニティの投稿一覧を、Hot スコアの高い順に並べて取り出す」という読み方です。コミュニティでの絞り込み（`subreddit_id`）と並び替え（`hot_score`）の両方に効く組で索引を作っています。
4. アプリ側の確認は、同時に2つの登録リクエストが来た場合に、両方とも「まだ無い」と判断してすり抜けることがあるためです。DB のユニークインデックスは最後の砦として、重複した行の保存そのものを防ぎます。
