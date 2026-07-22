from fastapi import Header, HTTPException, status

from app.core.auth_cache import auth_cache


async def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """从 Authorization 请求头读取 auth_code，并从认证缓存中解析用户 ID。"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization，请先登录",
        )

    auth_code = authorization.strip()
    if not auth_code:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 Authorization，请先登录",
        )

    user_id = await auth_cache.get(auth_code)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态无效或已过期，请重新登录",
        )

    return user_id
