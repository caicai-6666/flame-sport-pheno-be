from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.point_record import PointRecord
from app.models.product import Product


class ShopRepository:
    async def get_visible_product_by_id(
        self,
        session: AsyncSession,
        product_id: int,
    ) -> Product | None:
        """根据商品 ID 查询上架商品。"""
        result = await session.execute(
            select(Product)
            .where(Product.id == product_id)
            .where(Product.status == 1)
        )
        return result.scalar_one_or_none()

    async def list_visible_products(self, session: AsyncSession) -> list[Product]:
        """查询所有上架商品。"""
        result = await session.execute(
            select(Product).where(Product.status == 1)
        )
        return list(result.scalars().all())

    async def list_user_point_records(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> list[tuple[PointRecord, str | None]]:
        """查询指定用户有效积分流水，商品名为空时表示非兑换流水。"""
        result = await session.execute(
            select(PointRecord, Product.name)
            .select_from(PointRecord)
            .outerjoin(Product, Product.id == PointRecord.product_id)
            .where(PointRecord.user_id == user_id)
            .where(PointRecord.status == 1)
        )
        return list(result.all())

    async def get_latest_effective_point_record(
        self,
        session: AsyncSession,
        user_id: str,
    ) -> PointRecord | None:
        """查询用户最后一条有效积分流水，用于获取当前积分余额。"""
        result = await session.execute(
            select(PointRecord)
            .where(PointRecord.user_id == user_id)
            .where(PointRecord.status == 1)
            .order_by(PointRecord.created_at.desc(), PointRecord.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_exchange_point_record(
        self,
        session: AsyncSession,
        user_id: str,
        product_id: int,
        change_points: int,
        points_after: int,
        description: str,
    ) -> PointRecord:
        """创建商品兑换积分扣减流水。"""
        point_record = PointRecord(
            user_id=user_id,
            product_id=product_id,
            change_type="exchange",
            change_points=change_points,
            points_after=points_after,
            description=description,
            status=1,
        )
        session.add(point_record)
        await session.flush()
        return point_record


shop_repository = ShopRepository()
