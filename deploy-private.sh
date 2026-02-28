#!/bin/bash
# 私有项目 - Ubuntu 服务器部署脚本
# 使用方法: 将构建好的镜像 tar.gz 文件放在同一目录后执行

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_FILE=""
IMAGE_NAME="seed-scanner"
SMB_SERVER=""
SMB_SHARE=""
SMB_USER=""
SMB_PASS=""

echo "=========================================="
echo "  Seed Scanner 私有部署"
echo "=========================================="
echo ""

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 查找镜像文件
if [ -f "$SCRIPT_DIR/seed-scanner-*.tar.gz" ]; then
    IMAGE_FILE=$(ls -t $SCRIPT_DIR/seed-scanner-*.tar.gz | head -1)
    echo "找到镜像文件: $IMAGE_FILE"
elif [ -f "$SCRIPT_DIR/seed-scanner-*.tar" ]; then
    IMAGE_FILE=$(ls -t $SCRIPT_DIR/seed-scanner-*.tar | head -1)
    echo "找到镜像文件: $IMAGE_FILE"
else
    echo "错误: 未找到镜像文件 (seed-scanner-*.tar.gz)"
    echo "请先运行 build-private.sh 生成镜像文件"
    exit 1
fi

# 询问 SMB 信息
if [ -z "$SMB_SERVER" ]; then
    read -p "SMB 服务器地址 (如: 192.168.1.100): " SMB_SERVER
fi
if [ -z "$SMB_SHARE" ]; then
    read -p "SMB 共享名称 (如: share): " SMB_SHARE
fi
if [ -z "$SMB_USER" ]; then
    read -p "SMB 用户名: " SMB_USER
fi
if [ -z "$SMB_PASS" ]; then
    read -sp "SMB 密码: " SMB_PASS
    echo ""
fi

echo ""
echo "[1/6] 安装 Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker $SUDO_USER
else
    echo "Docker 已安装"
fi

echo ""
echo "[2/6] 安装 Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose 已安装"
fi

echo ""
echo "[3/6] 安装 SMB 工具..."
apt-get update -qq
apt-get install -y -qq cifs-utils

echo ""
echo "[4/6] 导入 Docker 镜像..."
if [[ $IMAGE_FILE == *.gz ]]; then
    echo "解压镜像..."
    gunzip -c "$IMAGE_FILE" > /tmp/seed-scanner.tar
    docker load -i /tmp/seed-scanner.tar
    rm -f /tmp/seed-scanner.tar
else
    docker load -i "$IMAGE_FILE"
fi

echo ""
echo "[5/6] 配置 SMB 挂载..."
mkdir -p /mnt/xspt

# 创建 SMB 凭证文件
echo "username=$SMB_USER" > /root/.smbcredentials
echo "password=$SMB_PASS" >> /root/.smbcredentials
chmod 600 /root/.smbcredentials

# 配置自动挂载
if ! grep -q "/mnt/xspt" /etc/fstab; then
    echo "//$SMB_SERVER/$SMB_SHARE /mnt/xspt cifs credentials=/root/.smbcredentials,iocharset=utf8,vers=3.0,_netdev 0 0" >> /etc/fstab
fi

# 立即挂载
mount -a || echo "警告: SMB 挂载失败，请检查配置"

echo ""
echo "[6/6] 创建工作目录..."
mkdir -p /opt/seed-scanner
cd /opt/seed-scanner

# 创建 docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  seed-scanner:
    image: seed-scanner:latest
    container_name: seed-scanner
    volumes:
      - /mnt/xspt:/scan:ro
      - ./output:/app/output
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
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

mkdir -p output data

echo ""
echo "=========================================="
echo "✓ 部署完成!"
echo "=========================================="
echo ""
echo "工作目录: /opt/seed-scanner"
echo ""
echo "使用命令:"
echo "  cd /opt/seed-scanner"
echo "  docker-compose up                    # 运行扫描"
echo "  docker-compose run --rm seed-scanner /scan --force  # 强制重新扫描"
echo "  docker-compose logs -f               # 查看日志"
echo ""
echo "设置定时任务:"
echo "  crontab -e"
echo "  0 */6 * * * cd /opt/seed-scanner && docker-compose up --abort-on-container-exit"
echo ""
