# Docker Hub 部署指南

## 方案概述

1. **本地/CI 构建** → 推送到 Docker Hub
2. **服务器直接拉取** → 无需在服务器上构建

---

## 第一步：推送镜像到 Docker Hub

### 1. 修改构建脚本

编辑 `build-and-push.sh`，设置你的 Docker Hub 用户名：

```bash
DOCKERHUB_USER="your-username"  # 修改这里
```

### 2. 登录 Docker Hub

```bash
docker login
# 输入你的 Docker Hub 用户名和密码
```

### 3. 执行构建和推送

```bash
chmod +x build-and-push.sh
./build-and-push.sh
```

输出示例：
```
==========================================
  Seed Scanner Docker 构建脚本
==========================================

镜像名称: seed-scanner
版本: 0.1.0
Docker Hub: yourname/seed-scanner

✓ 推送完成!
==========================================

镜像地址:
  yourname/seed-scanner:latest
  yourname/seed-scanner:0.1.0
```

---

## 第二步：服务器端部署

### 1. 登录服务器

```bash
ssh user@your-ubuntu-server
```

### 2. 一键部署脚本

在服务器上创建 `deploy.sh`：

```bash
#!/bin/bash
set -e

DOCKERHUB_USER="your-username"  # 修改为你的用户名
SMB_SERVER="your-nas-ip"
SMB_SHARE="your-share-name"
SMB_USER="your-smb-username"
SMB_PASS="your-smb-password"

echo "=== Seed Scanner 服务器部署 ==="

# 安装 Docker（如果未安装）
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
fi

# 安装 Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "安装 Docker Compose..."
    sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# 安装 SMB 工具
sudo apt-get update
sudo apt-get install -y cifs-utils

# 创建挂载点
sudo mkdir -p /mnt/xspt

# 配置 SMB 自动挂载
echo "//$SMB_SERVER/$SMB_SHARE /mnt/xspt cifs credentials=/root/.smbcredentials,iocharset=utf8,vers=3.0,_netdev 0 0" | sudo tee -a /etc/fstab

# 创建 SMB 凭证文件
echo "username=$SMB_USER" | sudo tee /root/.smbcredentials
echo "password=$SMB_PASS" | sudo tee -a /root/.smbcredentials
sudo chmod 600 /root/.smbcredentials

# 挂载 SMB
sudo mount -a

# 创建工作目录
mkdir -p ~/seed-scanner
cd ~/seed-scanner

# 创建 docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  seed-scanner:
    image: ${DOCKERHUB_USER}/seed-scanner:latest
    container_name: seed-scanner
    volumes:
      - /mnt/xspt:/scan:ro
      - ./output:/app/output
      - ./data:/app/data
    environment:
      - PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
      - TZ=Asia/Shanghai
    command: ["/scan", "--config", "/app/config.yaml"]
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          memory: 2G
    restart: "no"
EOF

# 创建 config.yaml
cat > config.yaml << 'EOF'
scanner:
  supported_formats: [".png", ".jpg", ".jpeg", ".bmp", ".webp"]
  recursive: true

ocr:
  use_gpu: false
  lang: "en"

detection:
  seed_lengths: [12, 24]
  fuzzy_threshold: 1

mail:
  enabled: false
  smtp_server: "smtp.example.com"
  smtp_port: 587
  username: ""
  password: ""
  to_address: ""
  subject: "助记词扫描结果"

output:
  directory: "/app/output"
  generate_json: true
  generate_txt: true

database:
  path: "/app/data/seed_scanner.db"
EOF

# 拉取镜像
echo "拉取镜像..."
docker pull ${DOCKERHUB_USER}/seed-scanner:latest

# 创建目录
mkdir -p output data

echo ""
echo "=== 部署完成 ==="
echo ""
echo "使用方法:"
echo "  cd ~/seed-scanner"
echo "  docker-compose up              # 运行扫描"
echo "  docker-compose up --force      # 强制重新扫描"
echo ""
```

### 3. 运行部署脚本

```bash
chmod +x deploy.sh
sudo ./deploy.sh
```

---

## 第三步：服务器日常使用

```bash
cd ~/seed-scanner

# 手动运行扫描
docker-compose up

# 强制重新扫描
docker-compose run --rm seed-scanner /scan --force

# 查看日志
docker-compose logs -f

# 更新镜像（有新版本时）
docker-compose pull
docker-compose up
```

---

## 定时自动扫描

创建 systemd 定时任务：

```bash
# 创建定时器
sudo tee /etc/systemd/system/seed-scanner.timer << 'EOF'
[Unit]
Description=Run Seed Scanner every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# 创建服务
sudo tee /etc/systemd/system/seed-scanner.service << 'EOF'
[Unit]
Description=Seed Scanner
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/home/your-user/seed-scanner
ExecStart=/usr/local/bin/docker-compose up --abort-on-container-exit

[Install]
WantedBy=multi-user.target
EOF

# 启用定时器
sudo systemctl daemon-reload
sudo systemctl enable seed-scanner.timer
sudo systemctl start seed-scanner.timer

# 查看状态
sudo systemctl status seed-scanner.timer
```

---

## 备选：不使用 Docker Compose

```bash
# 直接运行
docker run --rm \
  -v /mnt/xspt:/scan:ro \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/data:/app/data \
  -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
  your-username/seed-scanner:latest \
  /scan --config /app/config.yaml
```

---

## 文件清单

| 文件 | 用途 |
|------|------|
| `build-and-push.sh` | 本地构建并推送到 Docker Hub |
| `Dockerfile.slim` | 精简版 Dockerfile |
| `docker-compose.server.yml` | 服务器端使用 |
| `deploy.sh` | 服务器一键部署脚本 |
