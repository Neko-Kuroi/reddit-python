# app/comments/models.py
import uuid
from typing import ClassVar
from sqlalchemy import Text, Integer, UUID, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuid_generate_v4()")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True  # トップレベルのコメントは None
    )

    # アソシエーション
    author: Mapped["User"] = relationship("User", back_populates="comments")
    post: Mapped["Post"] = relationship("Post", back_populates="comments")
    parent: Mapped["Comment | None"] = relationship(
        "Comment", back_populates="replies", remote_side="Comment.id"
    )
    replies: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="parent"
    )

    # ツリー構造用（Python側でセットする）
    # カラムではないので ClassVar で宣言し、実体は __init__ で
    # インスタンス属性として初期化する
    # （クラス属性に list の既定値を置くと全インスタンスで共有されてしまう）
    children: ClassVar[list["Comment"]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.children = []

    def __repr__(self) -> str:
        return f"<Comment {str(self.id)[:8]}>"
