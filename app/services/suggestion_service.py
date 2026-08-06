from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.suggestion_repository import suggestion_repository
from app.repositories.user_repository import user_repository


class SuggestionService:
    async def create_remark(
        self,
        user_id: str,
        remark: str,
        session: AsyncSession,
    ) -> dict[str, int | str]:
        """保存当前登录用户提交的建议。"""
        content = remark.strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="建议内容不能为空",
            )

        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        try:
            # 显式校验用户存在，避免外键错误以数据库异常形式泄露给接口调用方。
            suggestion = await suggestion_repository.create(
                session=session,
                user_id=user_id,
                content=content,
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return {
            "id": suggestion.id or 0,
            "created_at": suggestion.created_at.isoformat(timespec="seconds"),
        }


suggestion_service = SuggestionService()
