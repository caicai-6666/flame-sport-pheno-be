from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.user import User


class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id: str) -> User | None:
        """根据用户 ID 查询用户。"""
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def lock_by_id(self, session: AsyncSession, user_id: str) -> User | None:
        """通过行锁锁定用户记录，串行化同一用户的积分扣减。"""
        result = await session.execute(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, user: User) -> User:
        """创建首次登录时初始化的用户。"""
        session.add(user)
        await session.flush()
        return user


user_repository = UserRepository()
