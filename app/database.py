# app/database.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# 非同期エンジンを作成する
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,   # DEBUG=True のとき SQL をログに出力する
    pool_size=10,
    max_overflow=20
)

# セッションファクトリー
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False   # コミット後もオブジェクトにアクセスできる
)

# 全モデルの基底クラス
class Base(DeclarativeBase):
    pass

# DB セッションを取得する（Depends で使う）
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# === appended from chapter_03a.md block 2 ===
# app/database.py に追加
import uuid
from sqlalchemy import DateTime, func
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime

class TimestampMixin:
    """inserted_at / updated_at を自動管理するミックスイン"""
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
