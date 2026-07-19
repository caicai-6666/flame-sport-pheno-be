class CurrentSeasonRuntime:
    """当前进程内的赛季运行时缓存。

    该类只保存当前激活赛季的轻量配置，不在应用冷启动时主动初始化。
    当业务接口首次需要当前赛季信息时，再从数据库读取并写入这里。
    """

    # 当前激活赛季 ID。None 表示尚未初始化。
    season_id: int | None = None

    # 当前激活赛季要求用户锁定的项目数量。None 表示尚未初始化。
    required_project_count: int | None = None

    @classmethod
    def set(cls, season_id: int, required_project_count: int) -> None:
        """设置当前进程内的赛季运行时缓存。"""
        cls.season_id = season_id
        cls.required_project_count = required_project_count

    @classmethod
    def is_initialized(cls) -> bool:
        """判断当前赛季运行时缓存是否已经初始化。"""
        return cls.season_id is not None and cls.required_project_count is not None
