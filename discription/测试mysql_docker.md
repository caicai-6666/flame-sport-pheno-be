# 1. 构建 MySQL 镜像
docker build -f Dockerfile.mysql -t flame-winter-pheno-mysql:8.4 .

# 2. 创建数据卷
docker volume create flame-winter-pheno-mysql-data

# 3. 启动容器，映射到本机 3307 端口
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

本地连接参数：
host: 127.0.0.1
port: 3307
database: flame_winter_pheno
user: flame
password: flame123456
root password: root123456