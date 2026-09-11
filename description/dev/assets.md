# 本地资源目录说明

## 根目录

```text
assets/
  images/
    avatar/
    product/
    project_icon/
    proof_record/
    poster/
```

本地直接运行时，资源位于后端仓库的 `assets/`。Docker Compose 部署时，后端项目根目录为 `/workspace`，资源目录位于与 Python 包 `/workspace/app` 平级的 `/workspace/assets`，并由具名卷 `backend_assets` 持久化，以避免频繁拉取或重建后端工作区影响上传文件。

图片读取接口使用应用内置的扩展名与 MIME 类型映射。即使精简容器没有 `/etc/mime.types`，WebP 文件仍必须返回 `Content-Type: image/webp`，不能降级为 `application/octet-stream`；JPEG、PNG 和 GIF 使用相同的稳定映射。

---

## poster

活动海报使用固定文件：

```text
assets/images/poster/活动规则.webp
```

客户端登录后通过 `GET /flame/api/image/poster` 读取，管理端通过 Docker 内部的 `GET /flame/api/admin/poster` 预览。两个接口都不接收路径参数，避免读取其他本地资源。

管理端通过 `POST /flame/api/admin/poster` 覆盖海报。上传源文件可以是 JPEG、PNG 或 WebP，最大 10 MiB；服务端修正 EXIF 方向并以质量 `90` 统一重编码为 WebP，固定文件名不会随上传文件名变化。写入使用同目录临时文件进行原子替换，覆盖期间的读取请求不会得到不完整文件。

客户端海报地址不会变化，因此响应使用 `private, no-cache`，要求浏览器重新确认固定资源是否更新。管理端预览使用 `private, no-store`。

Docker Compose 的 `backend_assets` 卷挂载整个 `/workspace/assets`。首次发布该功能时需要确认卷内已经存在 `/workspace/assets/images/poster/活动规则.webp`；代码仓库中的开发图片不会随镜像构建自动复制到该卷。

---

## avatar

用户头像目录：

```text
assets/images/avatar
```

首次钉钉登录初始化时，如钉钉返回头像地址，服务端会下载 JPEG、PNG 或 WebP 图片并统一转换为不超过 300 KiB 的 WebP。文件名为安全化后的钉钉 `userId` 加小写 `.webp`，例如：

```text
james.webp
```

`user.avatar_url` 保存带前导斜杠的相对路径，例如：

```text
/james.webp
```

转换会修正 EXIF 方向并保留透明通道；编码时优先降低 WebP 质量，仍超过限制时再逐步缩小像素尺寸。文件使用原子写入，如果后续用户初始化事务失败，则恢复覆盖前的头像或删除本次新文件。

现有用户头像已使用以下脚本迁移为 WebP。脚本复用新用户头像的质量与缩放策略，将单图控制在 300 KiB 内；转换前会备份原图，验证新文件后才删除旧扩展名文件：

```bash
python scripts/convert_avatar_images_to_webp.py \
  --source-dir assets/images/avatar \
  --backup-dir assets/backups/avatar_before_webp_YYYYMMDD
```

文件转换完成后执行 `scripts/migrations/20260814_convert_user_avatar_urls_to_webp.sql`，同步更新 `user.avatar_url`。生产环境使用 Docker 具名卷时，应先暂停新用户初始化，对 `/workspace/assets/images/avatar` 执行转换，再运行数据库迁移。

读取时会去除前导斜杠，再拼接目录：

```text
settings.AVATAR_IMAGE_DIR / user.avatar_url.lstrip("/")
```

---

## project_icon

项目图标目录：

```text
assets/images/project_icon
```

项目列表接口直接返回 `project.icon_url` 保存的相对地址，例如 `/跑步.webp`。前端再通过：

```text
GET /flame/api/image/project_icon?filename={encodeURIComponent(project.image)}
```

读取对应图片文件。

新图标可通过以下接口写入：

```text
POST /flame/api/admin/project_icon
```

该写入接口仅通过 Docker 内部的 `admin` 路由管理端调用。接口接受 JPEG、PNG 或 WebP，但 `icon_url` 必须以 `.webp` 结尾；服务端校验最长边不超过 1600 像素后，在线程池中无损编码为 WebP，并使用同目录临时文件原子替换目标文件。上传限制为 5 MiB。

现有项目图标可通过以下脚本无损转换。脚本会先保留原目录结构备份，再删除旧扩展名文件：

```bash
python scripts/convert_project_icons_to_webp.py \
  --source-dir assets/images/project_icon \
  --backup-dir assets/backups/project_icon_before_webp_YYYYMMDD
```

转换完成后执行 `scripts/migrations/20260814_convert_project_icon_urls_to_webp.sql`，同步更新 `project.icon_url`。生产环境使用 Docker 具名卷时，应先暂停项目图标写入，对 `/workspace/assets/images/project_icon` 执行转换，再运行数据库迁移。

由于读取接口存在浏览器缓存，更换图标时应优先使用新的唯一文件名，避免同一 `icon_url` 覆盖后客户端继续显示旧图。

---

## product

商品图片目录：

```text
assets/images/product
```

商城信息接口只返回 `product.image_url` 字符串，不返回图片文件。

示例：

```text
/Keep 弹力带.webp
```

前端请求商品图片时应使用：

```text
GET /flame/api/image/product?filename={encodeURIComponent(product.image_url)}
```

后端会去掉前导 `/` 或 `\`，再拼接到 `settings.PRODUCT_IMAGE_DIR`。

管理端已取得商品的 `image_url` 后，可通过 Docker 内部接口读取同一目录中的奖品图片：

```text
GET /flame/api/admin/product?image_url={encodeURIComponent(product.image_url)}
```

管理端可通过以下接口上传并替换奖品图片：

```text
POST /flame/api/admin/product/replace
```

该接口使用 `multipart/form-data` 同时接收新图片、新地址和可选的旧地址。服务端校验 JPEG、PNG 或 WebP 内容后先原子写入新图，再删除不同地址下的旧图片。旧地址为空时按首次新建处理；旧文件已不存在时也允许安全重试。该接口不修改 `product.image_url`，数据库记录由管理端业务接口单独更新。

当前商品图已统一使用 WebP，既能显著减小传输体积，也能保留原 PNG 图片的透明通道。批量转换脚本保持原始像素尺寸，默认使用质量 82；转换前会将 JPEG、PNG 原图备份到 `assets/backups/`，确认新文件可以正常解码后才删除旧扩展名文件。

本地转换命令：

```bash
python scripts/convert_product_images_to_webp.py \
  --source-dir assets/images/product \
  --backup-dir assets/backups/product_before_webp_YYYYMMDD
```

转换后还需要执行 `scripts/migrations/20260813_convert_product_image_urls_to_webp.sql`，同步更新 `product.image_url`，否则接口仍会按旧扩展名定位图片。

对于已经写入 Docker 具名卷的生产图片，可将脚本复制进正在运行的后端容器后执行：

```bash
docker cp scripts/convert_product_images_to_webp.py flame-sport-pheno-backend-1:/tmp/
docker exec flame-sport-pheno-backend-1 python /tmp/convert_product_images_to_webp.py \
  --source-dir /workspace/assets/images/product \
  --backup-dir /workspace/assets/backups/product_before_webp_YYYYMMDD
```

---

## proof_record

凭证图片目录：

```text
assets/images/proof_record/{season_id}
```

上传接口生成的文件名：

```text
{user_id}-{project_id}-{timestamp}-{上传文件主名}.webp
```

数据库当前只保存完整文件名，例如：

```text
bb123456-3-20260606090020-健身.webp
```

上传接口接受 JPEG、PNG 或 WebP 图片，并在服务端按质量 82 统一重编码为 WebP。转换保持原始像素尺寸，修正 EXIF 方向并支持透明通道；最终文件使用原子写入，数据库事务失败时会清理新文件。

凭证仍保存为单张 WebP，分段信息保存在 `proof_record.image_segments`，不另写 JSON 文件或切片文件。定位坐标基于修正 EXIF 方向后的最终图片尺寸；上传和补交均在定位校验通过后创建目录和保存文件。初审 Service 在线程池中读取整图并校验分段定位，将图片字节与定位交给工作流；旧记录保持空定位。工作流首节点根据定位生成无损 WebP 内存切片，保留尺寸、序号和原图坐标；历史图片没有定位时复用整图字节。处理不落盘、不改变原图，现有模型节点仍不使用图片。

历史图片转换前会按原有赛季目录结构备份原图。开发环境执行：

```bash
python scripts/convert_proof_record_images_to_webp.py \
  --source-dir assets/images/proof_record \
  --backup-dir assets/backups/proof_record_before_webp_YYYYMMDD
```

文件转换成功后，执行 `scripts/migrations/20260813_convert_proof_record_image_urls_to_webp.sql`，同步更新 `proof_record.image_url`。生产环境应先暂停凭证上传，再对 `/workspace/assets/images/proof_record` 所在具名卷执行相同转换，最后运行数据库迁移，避免文件名和数据库地址短暂不一致。

确认激活赛季时会自动创建对应的 `{season_id}` 子目录；上传时会再次检查，以支持资源目录被运维清理后的恢复。

---

## 路径安全

头像、项目图标、商品图片、凭证图片和活动海报读取时都应确保路径没有逃逸出对应资源目录。
