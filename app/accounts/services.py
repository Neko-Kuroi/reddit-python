# app/accounts/services.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext

from app.accounts.models import User
from app.accounts.schemas import UserCreate

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ----------------------------------------------------------------
# ユーザー登録
# ----------------------------------------------------------------

async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """
    ユーザーを登録する。
    パスワードをハッシュ化してから保存する。
    """
    # 大文字小文字を区別しないよう、保存前に小文字へそろえる
    username = data.username.lower()
    email = data.email.lower()

    # username と email の重複チェック
    existing = await db.execute(
        select(User).where(
            (User.username == username) | (User.email == email)
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("このユーザー名またはメールアドレスはすでに使われています")

    user = User(
        username=username,
        email=email,
        password_hash=pwd_context.hash(data.password)
    )
    db.add(user)
    try:
        await db.flush()   # ID を確定させる（commit はしない）
        await db.refresh(user)
    except IntegrityError:
        # 重複チェック後に別のリクエストが先に登録した場合は、
        # DB の一意制約違反を 500 ではなく重複エラーとして返す
        await db.rollback()
        raise ValueError("このユーザー名またはメールアドレスはすでに使われています")
    return user


# ----------------------------------------------------------------
# ログイン
# ----------------------------------------------------------------

async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> User | None:
    """
    メールとパスワードでユーザーを認証する。
    失敗理由は曖昧にする（セキュリティ上の理由）。
    """
    result = await db.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()

    if user is None:
        # タイミング攻撃対策：ユーザーが存在しなくてもハッシュ計算を行う
        pwd_context.dummy_verify()
        return None

    if not pwd_context.verify(password, user.password_hash):
        return None

    return user


# ----------------------------------------------------------------
# ユーザー取得
# ----------------------------------------------------------------

async def get_user_by_id(db: AsyncSession, user_id: str | uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username.lower()))
    return result.scalar_one_or_none()


# ----------------------------------------------------------------
# Karma の更新
# ----------------------------------------------------------------

async def update_karma(
    db: AsyncSession, user_id: uuid.UUID, karma_type: str, amount: int
) -> None:
    """
    Karma を増減する。
    投票されたときに Posts / Comments Service から呼ばれる。
    DB レベルで直接更新することで競合を防ぐ。
    """
    if karma_type == "post":
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(post_karma=User.post_karma + amount)
        )
    elif karma_type == "comment":
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(comment_karma=User.comment_karma + amount)
        )
