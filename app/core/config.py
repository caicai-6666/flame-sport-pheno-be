from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # 固定读取项目根目录配置，避免从 app/ 或 IDE 启动时落到不同路径。
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "flame-sport-pheno-be"
    # 生产模式使用钉钉免登；开发模式仅以 auth_code 查询本地 user.id。
    APP_MODE: Literal["production", "development"] = "production"
    BASE_DIR: Path = PROJECT_ROOT
    ASSETS_DIR: Path = BASE_DIR / "assets"
    IMAGE_ASSETS_DIR: Path = ASSETS_DIR / "images"
    AVATAR_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "avatar"
    PROJECT_ICON_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "project_icon"
    PRODUCT_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "product"
    PROOF_RECORD_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "proof_record"
    POSTER_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "poster"
    DATABASE_URL: str = "mysql+asyncmy://flame:flame123456@127.0.0.1:3307/flame_sport_pheno?charset=utf8mb4"
    DB_ECHO: bool = False
    AUTH_CACHE_TTL_SECONDS: int = 7200
    AUTH_CACHE_CLEANUP_INTERVAL_SECONDS: int = 300
    DINGTALK_CLIENT_ID: str | None = None
    DINGTALK_CLIENT_SECRET: str | None = None
    DINGTALK_AGENT_ID: int | None = None
    DINGTALK_HTTP_TIMEOUT_SECONDS: float = 5.0
    DINGTALK_ACCESS_TOKEN_REFRESH_INTERVAL_SECONDS: int = 300
    DINGTALK_ACCESS_TOKEN_REFRESH_SKEW_SECONDS: int = 300
    DINGTALK_NOTIFICATION_CHECK_INTERVAL_SECONDS: int = 60
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_HTTP_TIMEOUT_SECONDS: float = 60.0
    # 初审任务默认关闭，避免仅配置密钥后即在部署环境产生模型调用费用。
    LLM_PRELIMINARY_REVIEW_ENABLED: bool = False
    LLM_PRELIMINARY_REVIEW_INTERVAL_SECONDS: int = 900
    LLM_PRELIMINARY_REVIEW_MIN_AGE_SECONDS: int = 300
    # 补偿多次四位小数增量累计产生的尾差；0 表示关闭自动补足。
    PROGRESS_COMPLETION_SNAP_THRESHOLD: Decimal = Field(
        default=Decimal("0.0001"),
        ge=Decimal("0"),
        le=Decimal("0.005"),
    )
    SEASON_PARTICIPATION_ALLOWED_DAYS: int = 7
    # 赛季开始后的配置保护期内暂停客户业务写入，零表示不冻结。
    ACTIVE_SEASON_CONFIG_EDIT_WINDOW_HOURS: int = Field(default=24, ge=0)
    LEADERBOARD_REFRESH_ENABLED: bool = True
    LEADERBOARD_REFRESH_ON_STARTUP: bool = True
    LEADERBOARD_REFRESH_INTERVAL_SECONDS: int = 900
    # 头像、商品图和项目图标的浏览器私有缓存时长；凭证图片固定不缓存。
    IMAGE_CACHE_MAX_AGE_SECONDS: int = 604800


settings = Settings()
