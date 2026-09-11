"""准备初审任务的图片输入，不切片、不调用模型。"""

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from app.agent.preliminary_review.schemas import PreliminaryReviewImage
from app.core.config import settings
from app.core.image_segments import validate_image_segments


def load_review_image(path: Path, segments: dict[str, Any] | None) -> PreliminaryReviewImage:
    resolved = path.resolve()
    if not resolved.is_relative_to(settings.PROOF_RECORD_IMAGE_DIR.resolve()):
        raise ValueError("凭证图片路径非法")
    content = resolved.read_bytes()
    try:
        with Image.open(BytesIO(content)) as image:
            media_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
            if media_type is None:
                raise ValueError("凭证图片格式不受支持")
            image.verify()
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("凭证图片内容无效") from exc
    normalized = validate_image_segments(json.dumps(segments) if segments is not None else None, content)
    return PreliminaryReviewImage(content=content, media_type=media_type, image_segments=normalized)
