# Ubuntu 服务器部署指南（GitHub 同步）

## 前置要求

- Ubuntu 20.04/22.04 服务器
- 已挂载 SMB 共享目录
- 服务器可访问 GitHub

## 部署步骤

### 1. 服务器克隆项目

```bash
# SSH 登录服务器
ssh root@你的服务器IP

# 克隆项目（私有仓库需要配置 SSH key）
git clone git@github.com:你的用户名/seed-scanner.git /opt/seed-scanner

# 或使用 HTTPS（需要输入密码/token）
# git clone https://github.com/你的用户名/seed-scanner.git /opt/seed-scanner

cd /opt/seed-scanner
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env

# 编辑配置
vim .env
```

修改为你的实际路径：

```bash
# SMB 挂载的扫描目录
SCAN_PATH=/mnt/xspt

# 项目目录（当前目录）
PROJECT_PATH=/opt/seed-scanner
```

### 3. 确保 SMB 已挂载

```bash
# 检查挂载
ls -la /mnt/xspt

# 如果未挂载，手动挂载：
mount -t cifs //NAS_IP/share /mnt/xspt -o username=xxx,password=xxx,iocharset=utf8
```

### 4. 构建并运行

```bash
# 首次构建镜像
docker-compose build

# 运行扫描
docker-compose up

# 后台运行
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 日常使用

### 更新代码

```bash
cd /opt/seed-scanner
git pull origin main

# 如果代码有更新，重新构建
docker-compose build
docker-compose up
```

### 强制重新扫描

```bash
docker-compose run --rm seed-scanner /scan --force
```

### 定时自动扫描

```bash
# 编辑 crontab
crontab -e

# 每 6 小时扫描一次
0 */6 * * * cd /opt/seed-scanner && docker-compose up -d

# 或每天凌晨 2 点扫描
0 2 * * * cd /opt/seed-scanner && /usr/local/bin/docker-compose up -d
```

### 查看结果

```bash
# JSON 报告
ls -la output/*.json

# TXT 报告
ls -la output/*.txt

# 查看最新报告
cat output/scan_result_*.txt
```

## 多实例部署

如果需要扫描多个目录：

```bash
# 实例 1: 扫描照片
mkdir -p /opt/seed-scanner-photos
cp /opt/seed-scanner/.env /opt/seed-scanner-photos/
# 修改 .env: SCAN_PATH=/mnt/photos

# 实例 2: 扫描文档
mkdir -p /opt/seed-scanner-docs
cp /opt/seed-scanner/.env /opt/seed-scanner-docs/
# 修改 .env: SCAN_PATH=/mnt/documents
```

## 故障排查

### SMB 挂载问题

```bash
# 检查挂载
mount | grep xspt

# 重新挂载
umount /mnt/xspt
mount -a
```

### 容器问题

```bash
# 查看容器状态
docker ps -a

# 查看日志
docker-compose logs

# 重启容器
docker-compose restart

# 完全重建
docker-compose down
docker-compose up --build
```

### 权限问题

```bash
# 确保目录权限正确
chmod 755 output data
```

## 完整命令速查

```bash
# 部署
ssh root@服务器IP
git clone git@github.com:用户名/seed-scanner.git /opt/seed-scanner
cd /opt/seed-scanner
cp .env.example .env
# 编辑 .env
docker-compose up --build

# 更新
git pull
docker-compose build
docker-compose up

# 管理
docker-compose logs -f              # 查看日志
docker-compose down                 # 停止
docker-compose up -d                # 后台运行
docker system prune -f              # 清理缓存
```
