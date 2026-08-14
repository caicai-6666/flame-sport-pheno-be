from datetime import datetime


class LeaderboardRuntime:
    """当前进程内的排行榜运行时状态。"""

    # 最近一次排行榜快照计算完成时间。None 表示当前进程尚未成功计算过。
    calculated_at: datetime | None = None

    @classmethod
    def set_calculated_at(cls, calculated_at: datetime) -> None:
        """记录最近一次排行榜快照计算完成时间。"""
        cls.calculated_at = calculated_at
