from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import auth_cache
from app.repositories.user_repository import user_repository


class AuthService:
    async def login_with_auth_code(
        self,
        auth_code: str,
        session: AsyncSession,
    ) -> str:
        """校验 auth_code 对应的用户，成功后写入认证缓存。"""
        normalized_auth_code = auth_code.strip()
        if not normalized_auth_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="auth_code 不能为空",
            )

        user_id = await self._resolve_user_id_from_auth_code(
            auth_code=normalized_auth_code,
        )
        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或无权限登录",
            )

        await auth_cache.set(
            auth_code=normalized_auth_code,
            user_id=user.id,
        )
        return normalized_auth_code

    async def _resolve_user_id_from_auth_code(self, auth_code: str) -> str:
        """测试阶段暂时将 auth_code 视为用户 ID；后续替换为外部接口调用。"""
        return auth_code


auth_service = AuthService()
