"""按已保存图片的像素坐标准备内存切片，不读写文件。"""

import json
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.agent.preliminary_review.schemas import PreliminaryReviewImage, PreparedReviewImage
from app.core.image_segments import validate_image_segments


def build_record_images(image: PreliminaryReviewImage) -> tuple[PreparedReviewImage, ...]:
    """裁剪前复用上传定位校验，避免 Pillow 对越界区域静默补黑。"""
    try:
        with Image.open(BytesIO(image.content)) as source:
            media_type = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(source.format)
            if media_type is None or media_type != image.media_type:
                raise ValueError("凭证图片格式不受支持或与媒体类型不一致")
            segments = validate_image_segments(
                json.dumps(image.image_segments) if image.image_segments is not None else None,
                image.content,
            )
            # 必须完整解码，不能只凭图片头接受损坏内容。
            source.load()
            if segments is None:
                # 历史图片没有可信切分位置时保留原始字节，避免猜测切分或重复有损编码。
                return (PreparedReviewImage(
                    index=1, x=0, y=0, width=source.width, height=source.height,
                    media_type=media_type, content=image.content,
                ),)

            prepared = []
            for index, segment in enumerate(segments["segments"], start=1):
                x, y, width, height = (segment[key] for key in ("x", "y", "width", "height"))
                with source.crop((x, y, x + width, y + height)) as crop:
                    with BytesIO() as output:
                        # 截图文字与透明通道保持原像素，不再施加一次有损压缩。
                        crop.save(output, format="WEBP", lossless=True, exact=True)
                        prepared.append(PreparedReviewImage(
                            index=index, x=x, y=y, width=width, height=height,
                            media_type="image/webp", content=output.getvalue(),
                        ))
            return tuple(prepared)
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ValueError("凭证图片无法解码或裁剪") from exc
