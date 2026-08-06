from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_suggestion import UserSuggestion


class SuggestionRepository:
    async def create(
        self,
        session: AsyncSession,
        user_id: str,
        content: str,
    ) -> UserSuggestion:
        """创建一条默认可见的用户建议。"""
        suggestion = UserSuggestion(user_id=user_id, content=content)
        session.add(suggestion)
        await session.flush()
        return suggestion


suggestion_repository = SuggestionRepository()
