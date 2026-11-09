# app/communities/models.py
import uuid
from datetime import datetime
from sqlalchemy import String, Text, UUID, ForeignKey, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class Subreddit(Base, TimestampMixin):
    __tablename__ = "subreddits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    name: Mapped[str] = mapped_column(String(21), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )

    # アソシエーション
    owner: Mapped["User"] = relationship("User", foreign_keys=[owner_id])
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="subreddit")
    members: Mapped[list["SubredditMember"]] = relationship(
        "SubredditMember", back_populates="subreddit"
    )

    def __repr__(self) -> str:
        return f"<Subreddit r/{self.name}>"


class SubredditMember(Base):
    __tablename__ = "subreddit_members"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    subreddit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subreddits.id", ondelete="CASCADE"),
        nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # アソシエーション
    user: Mapped["User"] = relationship("User", back_populates="subreddit_members")
    subreddit: Mapped["Subreddit"] = relationship(
        "Subreddit", back_populates="members"
    )

    def __repr__(self) -> str:
        return f"<SubredditMember user={self.user_id} subreddit={self.subreddit_id}>"
