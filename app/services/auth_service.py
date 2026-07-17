from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import auth_cache
from app.repositories.user_repository import user_repository


class AuthService:
    async def login_with_access_token(
        self,
        access_token: str,
        session: AsyncSession,
    ) -> str:
        """校验 access_token 对应的用户，成功后写入认证缓存。"""
        normalized_access_token = access_token.strip()
        if not normalized_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="access_token 不能为空",
            )

        user_id = await self._resolve_user_id_from_access_token(
            access_token=normalized_access_token,
        )
        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或无权限登录",
            )

        await auth_cache.set(
            access_token=normalized_access_token,
            user_id=user.id,
        )
        return normalized_access_token

    async def _resolve_user_id_from_access_token(self, access_token: str) -> str:
        """测试阶段暂时将 access_token 视为用户 ID；后续替换为外部接口调用。"""
        return access_token


auth_service = AuthService()
