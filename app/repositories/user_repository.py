from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.user import User


class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id: str) -> User | None:
        """根据用户 ID 查询用户。"""
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()


user_repository = UserRepository()
