# MySQL Docker 说明

## 构建镜像

```bash
docker build -f Dockerfile.mysql -t flame-winter-pheno-mysql:8.4 .
```

## 创建数据卷

```bash
docker volume create flame-winter-pheno-mysql-data
```

## 启动容器

```bash
docker run -d \
  --name flame-winter-pheno-mysql \
  --restart unless-stopped \
  -p 3307:3306 \
  -v flame-winter-pheno-mysql-data:/var/lib/mysql \
  -e MYSQL_ROOT_PASSWORD=root123456 \
  -e MYSQL_DATABASE=flame_winter_pheno \
  -e MYSQL_USER=flame \
  -e MYSQL_PASSWORD=flame123456 \
  flame-winter-pheno-mysql:8.4
```

## 本地连接参数

```text
host: 127.0.0.1
port: 3307
database: flame_winter_pheno
user: flame
password: flame123456
root password: root123456
```

默认后端配置中的 `DATABASE_URL` 与上述连接参数一致。
