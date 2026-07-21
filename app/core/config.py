from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "flame-sport-pheno-be"
    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    ASSETS_DIR: Path = BASE_DIR / "assets"
    IMAGE_ASSETS_DIR: Path = ASSETS_DIR / "images"
    AVATAR_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "avatar"
    PROJECT_ICON_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "project_icon"
    PRODUCT_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "product"
    PROOF_RECORD_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "proof_record"
    DATABASE_URL: str = "mysql+asyncmy://flame:flame123456@127.0.0.1:3307/flame_sport_pheno?charset=utf8mb4"
    DB_ECHO: bool = False
    AUTH_CACHE_TTL_SECONDS: int = 7200
    AUTH_CACHE_CLEANUP_INTERVAL_SECONDS: int = 300
    SEASON_PARTICIPATION_ALLOWED_DAYS: int = 7
    LEADERBOARD_REFRESH_ENABLED: bool = True
    LEADERBOARD_REFRESH_ON_STARTUP: bool = True
    LEADERBOARD_REFRESH_INTERVAL_SECONDS: int = 86400


settings = Settings()
