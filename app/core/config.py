from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "flame-winter-pheno-be"
    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    ASSETS_DIR: Path = BASE_DIR / "assets"
    IMAGE_ASSETS_DIR: Path = ASSETS_DIR / "images"
    AVATAR_IMAGE_DIR: Path = IMAGE_ASSETS_DIR / "avatar"
    DATABASE_URL: str = "mysql+asyncmy://flame:flame123456@127.0.0.1:3307/flame_winter_pheno?charset=utf8mb4"
    DB_ECHO: bool = False
    AUTH_CACHE_TTL_SECONDS: int = 7200
    AUTH_CACHE_CLEANUP_INTERVAL_SECONDS: int = 300


settings = Settings()
