from fastapi import APIRouter

router = APIRouter(prefix="/user", tags=["user"])


@router.get("")
async def check_user_router():
    """用户子路由存活校验。"""
    return {"code": 200}
