import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.media_type import resolve_image_media_type


class ResolveImageMediaTypeTestCase(unittest.TestCase):
    # 验证 WebP 不依赖系统 MIME 数据库，覆盖精简 Docker 镜像中的生产故障。
    def test_resolves_webp_without_system_mime_database(self) -> None:
        with patch("app.core.media_type.mimetypes.guess_type") as guess_type:
            media_type = resolve_image_media_type(Path("avatar.webp"))

        self.assertEqual(media_type, "image/webp")
        guess_type.assert_not_called()

    # 验证所有允许的图片扩展名均使用稳定且大小写无关的内置映射。
    def test_resolves_supported_image_extensions(self) -> None:
        expected_media_types = {
            "image.GIF": "image/gif",
            "image.JPEG": "image/jpeg",
            "image.jpg": "image/jpeg",
            "image.PNG": "image/png",
            "image.WEBP": "image/webp",
        }

        for filename, expected_media_type in expected_media_types.items():
            with self.subTest(filename=filename):
                self.assertEqual(
                    resolve_image_media_type(filename),
                    expected_media_type,
                )

    # 未知扩展名继续使用安全兜底，避免响应头缺失或泄露不确定类型。
    def test_falls_back_for_unknown_extension(self) -> None:
        with patch(
            "app.core.media_type.mimetypes.guess_type",
            return_value=(None, None),
        ):
            media_type = resolve_image_media_type("image.unknown")

        self.assertEqual(media_type, "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
