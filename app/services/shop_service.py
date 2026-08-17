from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.shop_repository import shop_repository
from app.repositories.user_repository import user_repository
from app.services.user_write_guard import ensure_user_write_allowed


class ShopService:
    async def list_shop_products(
        self,
        session: AsyncSession,
    ) -> list[dict[str, int | str]]:
        """获取商城可见商品列表，只返回前端展示所需元数据。"""
        products = await shop_repository.list_visible_products(session=session)
        return [
            {
                "id": product.id or 0,
                "name": product.name,
                "description": product.description or "",
                "points_required": product.points_required,
                "image_url": product.image_url or "",
            }
            for product in products
        ]

    async def list_user_point_flow(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> list[dict[str, int | str]]:
        """获取当前用户有效积分流水列表。"""
        point_records = await shop_repository.list_user_point_records(
            session=session,
            user_id=user_id,
        )
        return [
            {
                "product_name": product_name or "",
                "change_type": point_record.change_type,
                "change_points": point_record.change_points,
                "points_after": point_record.points_after,
                "description": point_record.description or "",
                "created_at": point_record.created_at.isoformat(timespec="seconds"),
            }
            for point_record, product_name in point_records
        ]

    async def consume_product(
        self,
        user_id: str,
        product_id: int,
        session: AsyncSession,
    ) -> dict[str, int | str]:
        """兑换商品并写入积分扣减流水。"""
        try:
            await ensure_user_write_allowed(session=session)
        except Exception:
            await session.rollback()
            raise
        product = await shop_repository.get_visible_product_by_id(
            session=session,
            product_id=product_id,
        )
        if product is None or product.id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="商品不存在或已下架",
            )

        try:
            # 锁定用户行，避免同一用户并发兑换时同时基于旧余额扣减。
            locked_user = await user_repository.lock_by_id(
                session=session,
                user_id=user_id,
            )
            if locked_user is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="用户不存在",
                )

            latest_point_record = await shop_repository.get_latest_effective_point_record(
                session=session,
                user_id=user_id,
            )
            current_points = (
                latest_point_record.points_after
                if latest_point_record is not None
                else 0
            )
            if current_points < product.points_required:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="积分不足，无法兑换该商品",
                )

            points_after = current_points - product.points_required
            # 商品兑换只写入积分流水，不在当前阶段处理库存或订单。
            point_record = await shop_repository.create_exchange_point_record(
                session=session,
                user_id=user_id,
                product_id=product.id,
                change_points=-product.points_required,
                points_after=points_after,
                description=f"兑换商品：{product.name}",
            )
            await session.commit()
        except HTTPException:
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise

        return {
            "points_after": points_after,
            "created_at": point_record.created_at.isoformat(timespec="seconds"),
        }


shop_service = ShopService()
