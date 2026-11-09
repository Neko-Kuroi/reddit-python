# app/posts/models.py
import uuid
import math
from typing import ClassVar
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, UUID, ForeignKey, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)   # "text" | "link"
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hot_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    subreddit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subreddits.id", ondelete="CASCADE"),
        nullable=False
    )

    # アソシエーション
    author: Mapped["User"] = relationship(
        "User", back_populates="posts", foreign_keys=[author_id]
    )
    subreddit: Mapped["Subreddit"] = relationship(
        "Subreddit", back_populates="posts"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="post", cascade="all, delete-orphan"
    )
    votes: Mapped[list["Vote"]] = relationship(
        "Vote",
        primaryjoin="and_(Vote.target_type=='post', "
                    "foreign(Vote.target_id)==Post.id)",
        viewonly=True
    )

    # comment_count は DB に持たない（クエリで集計して Python 側でセットする）
    # カラムではないので ClassVar で宣言し、実体は __init__ で
    # インスタンス属性として初期化する
    comment_count: ClassVar[int]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.comment_count = 0

    @staticmethod
    def compute_hot_score(score: int, inserted_at: datetime) -> float:
        """Reddit オリジナルのアルゴリズムをシンプルにしたもの"""
        epoch = datetime(2005, 12, 8, 7, 46, 43, tzinfo=timezone.utc)
        order = math.log10(max(abs(score), 1))
        seconds = (inserted_at - epoch).total_seconds()
        return order + seconds / 45_000

    def __repr__(self) -> str:
        return f"<Post {self.title[:30]}>"


# === appended from chapter_03b.md block 5 ===
# app/posts/models.py に追加

class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    value: Mapped[int] = mapped_column(Integer, nullable=False)       # +1 | -1
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "post"|"comment"
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")
