import asyncio
import time
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class AuthCacheItem:
    user_id: str
    expires_at: float


class AuthCache:
    def __init__(self, default_ttl_seconds: int) -> None:
        self._default_ttl_seconds = default_ttl_seconds
        self._items: dict[str, AuthCacheItem] = {}
        self._lock = asyncio.Lock()

    async def set(
        self,
        auth_code: str,
        user_id: str,
        ttl_seconds: int | None = None,
    ) -> None:
        """写入 auth_code 和用户 ID 的缓存映射。"""
        expires_at = time.time() + (ttl_seconds or self._default_ttl_seconds)
        async with self._lock:
            self._items[auth_code] = AuthCacheItem(
                user_id=user_id,
                expires_at=expires_at,
            )

    async def get(self, auth_code: str) -> str | None:
        """根据 auth_code 读取用户 ID，命中有效缓存时自动续期。"""
        async with self._lock:
            item = self._items.get(auth_code)
            if item is None:
                return None

            now = time.time()
            if item.expires_at <= now:
                self._items.pop(auth_code, None)
                return None

            item.expires_at = now + self._default_ttl_seconds
            return item.user_id

    async def delete(self, auth_code: str) -> None:
        """删除指定 auth_code 的缓存。"""
        async with self._lock:
            self._items.pop(auth_code, None)

    async def cleanup_expired(self) -> None:
        """清理所有已过期的缓存。"""
        now = time.time()
        async with self._lock:
            expired_auth_codes = [
                auth_code
                for auth_code, item in self._items.items()
                if item.expires_at <= now
            ]
            for auth_code in expired_auth_codes:
                self._items.pop(auth_code, None)


auth_cache = AuthCache(default_ttl_seconds=settings.AUTH_CACHE_TTL_SECONDS)
_cleanup_task: asyncio.Task[None] | None = None


async def _cleanup_loop() -> None:
    """按固定间隔清理过期认证缓存。"""
    while True:
        await asyncio.sleep(settings.AUTH_CACHE_CLEANUP_INTERVAL_SECONDS)
        await auth_cache.cleanup_expired()


def start_auth_cache_cleanup_task() -> None:
    """启动认证缓存清理后台任务。"""
    global _cleanup_task
    if _cleanup_task is None or _cleanup_task.done():
        _cleanup_task = asyncio.create_task(_cleanup_loop())


async def stop_auth_cache_cleanup_task() -> None:
    """停止认证缓存清理后台任务。"""
    global _cleanup_task
    if _cleanup_task is None:
        return

    _cleanup_task.cancel()
    try:
        await _cleanup_task
    except asyncio.CancelledError:
        pass
    finally:
        _cleanup_task = None
