from app.core.config import settings


def ensure_asset_directories() -> None:
    settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.IMAGE_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.AVATAR_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
