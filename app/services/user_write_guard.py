"""统一限制赛季开始配置保护期内的客户业务写入。"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.season import Season
from app.repositories.season_repository import season_repository


BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


def get_user_write_window(
    start_date: date,
    edit_window_hours: int,
) -> tuple[datetime, datetime]:
    """返回上海时区下的保护期起止时刻，供强校验和只读提示共用同一口径。"""
    season_start_time = datetime.combine(
        start_date,
        time.min,
        tzinfo=BUSINESS_TIMEZONE,
    )
    return season_start_time, season_start_time + timedelta(hours=edit_window_hours)


def is_user_write_frozen(
    start_date: date,
    edit_window_hours: int,
    current_time: datetime | None = None,
) -> bool:
    """按上海时区判断当前时刻是否落在赛季开始后的配置保护期。"""
    if current_time is None:
        effective_current_time = datetime.now(BUSINESS_TIMEZONE)
    elif current_time.tzinfo is None:
        effective_current_time = current_time.replace(tzinfo=BUSINESS_TIMEZONE)
    else:
        effective_current_time = current_time.astimezone(BUSINESS_TIMEZONE)

    season_start_time, deadline = get_user_write_window(
        start_date=start_date,
        edit_window_hours=edit_window_hours,
    )
    # 提前激活的赛季仍允许抢先参与；达到截止时刻后立即恢复写入。
    return season_start_time <= effective_current_time < deadline


async def ensure_user_write_allowed(
    session: AsyncSession,
    current_time: datetime | None = None,
) -> Season | None:
    """在业务事务内锁定激活赛季，并拒绝配置保护期内的客户写入。"""
    active_seasons = await season_repository.lock_active_for_user_write(
        session=session,
    )
    if len(active_seasons) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="存在多个激活赛季，无法判断用户写入保护期",
        )
    if not active_seasons:
        return None

    active_season = active_seasons[0]
    if is_user_write_frozen(
        start_date=active_season.start_date,
        edit_window_hours=settings.ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS,
        current_time=current_time,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="赛季开始配置保护期内，暂不允许此操作",
        )
    return active_season
