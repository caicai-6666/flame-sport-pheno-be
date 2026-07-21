from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import user_repository


class UserService:
    async def update_profile(
        self,
        user_id: str,
        height_cm: float,
        session: AsyncSession,
    ) -> dict[str, float]:
        """更新当前用户资料。"""
        user = await user_repository.get_by_id(session=session, user_id=user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        normalized_height_cm = self._normalize_height_cm(height_cm)
        try:
            # 当前资料设置接口只更新身高，不修改登录态或其他用户基础信息。
            user.height_cm = normalized_height_cm
            await user_repository.update_height_cm(session=session, user=user)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        return {"height_cm": float(normalized_height_cm)}

    def _normalize_height_cm(self, height_cm: float) -> Decimal:
        """规范化身高数值，限制范围并保留两位小数。"""
        try:
            normalized_height_cm = Decimal(str(height_cm)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="height_cm 格式非法",
            ) from None

        if (
            normalized_height_cm < Decimal("50.00")
            or normalized_height_cm > Decimal("300.00")
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="height_cm 必须在 50 到 300 之间",
            )
        return normalized_height_cm


user_service = UserService()
