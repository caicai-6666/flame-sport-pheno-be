from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import get_current_user_id
from app.services.shop_service import shop_service

router = APIRouter(prefix="/shop", tags=["shop"])


@router.get("")
async def check_shop_router():
    """商城子路由存活校验。"""
    return {"code": 200}


@router.get("/product_info")
async def list_shop_products(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取商城可见商品列表。"""
    return await shop_service.list_shop_products(session=session)


@router.get("/point_flow")
async def list_user_point_flow(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户积分流水列表。"""
    return await shop_service.list_user_point_flow(
        user_id=user_id,
        session=session,
    )


@router.post("/consume")
async def consume_product(
    product_id: int = Body(..., ge=1, embed=True),
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """兑换指定商品并写入积分扣减流水。"""
    return await shop_service.consume_product(
        user_id=user_id,
        product_id=product_id,
        session=session,
    )
