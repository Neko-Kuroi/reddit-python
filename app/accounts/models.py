# app/accounts/models.py
import uuid
from sqlalchemy import String, Integer, UUID, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    post_karma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_karma: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # アソシエーション
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="author", foreign_keys="Post.author_id"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="author"
    )
    subreddit_members: Mapped[list["SubredditMember"]] = relationship(
        "SubredditMember", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"
