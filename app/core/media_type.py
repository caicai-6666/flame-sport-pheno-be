import mimetypes
from pathlib import Path


IMAGE_MEDIA_TYPES = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# 优先使用应用内置映射，避免精简容器缺少系统 MIME 数据库时错误降级。
def resolve_image_media_type(path: str | Path) -> str:
    image_path = Path(path)
    mapped_media_type = IMAGE_MEDIA_TYPES.get(image_path.suffix.lower())
    if mapped_media_type is not None:
        return mapped_media_type

    guessed_media_type = mimetypes.guess_type(image_path.name)[0]
    return guessed_media_type or "application/octet-stream"
