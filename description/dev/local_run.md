# 本地运行说明

## 技术栈

```text
FastAPI
SQLModel
SQLAlchemy AsyncSession
MySQL asyncmy
Pydantic Settings
```

## 依赖安装

```bash
pip install -r requirements.txt
```

文件上传接口依赖：

```text
python-multipart
```

## 配置

配置类位于：

```text
app/core/config.py
```

默认数据库连接：

```text
mysql+asyncmy://flame:flame123456@127.0.0.1:3307/flame_sport_pheno?charset=utf8mb4
```

可通过 `.env` 覆盖。

## 启动

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

`main.py` 中的直接运行配置当前使用固定局域网地址；本地开发更建议使用上面的 uvicorn 命令。

## 启动初始化

应用启动时会：

1. 创建本地资源目录。
2. 启动认证缓存过期清理任务。
3. 启动排行榜快照刷新任务。
4. 注册所有路由。

本地资源目录包括：

```text
assets/images/avatar
assets/images/project_icon
assets/images/product
assets/images/proof_record
```

排行榜刷新相关环境变量：

```text
LEADERBOARD_REFRESH_ENABLED=true
LEADERBOARD_REFRESH_ON_STARTUP=true
LEADERBOARD_REFRESH_INTERVAL_SECONDS=86400
```

本地调试时可以将 `LEADERBOARD_REFRESH_INTERVAL_SECONDS` 改小，例如 `60`。
