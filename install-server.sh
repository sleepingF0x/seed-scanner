#!/bin/bash
# 在 Ubuntu 服务器上直接构建并部署 Seed Scanner
# 使用方法: sudo ./install-server.sh [安装目录] [SMB挂载点]
# 示例: sudo ./install-server.sh /data/seed-scanner /data/nas-share

set -e

# 可配置的路径（通过参数或环境变量）
INSTALL_DIR="${1:-${INSTALL_DIR:-/opt/seed-scanner}}"
SMB_MOUNT="${2:-${SMB_MOUNT:-/mnt/xspt}}"

echo "=========================================="
echo "  Seed Scanner 服务器部署脚本"
echo "=========================================="
echo ""
echo "安装目录: $INSTALL_DIR"
echo "SMB挂载点: $SMB_MOUNT"
echo ""

# 检查 root 权限
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

# 检查内存
MEMORY_GB=$(free -g | awk '/^Mem:/{print $2}')
echo "检测到内存: ${MEMORY_GB}GB"

# 1. 安装基础依赖
echo ""
echo "[1/7] 安装基础依赖..."
apt-get update
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    cifs-utils

# 2. 安装 Docker
echo ""
echo "[2/7] 安装 Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "✓ Docker 安装完成"
else
    echo "✓ Docker 已安装"
fi

# 3. 准备项目目录
echo ""
echo "[3/7] 准备项目目录..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 4. 获取代码
echo ""
echo "[4/7] 获取项目代码..."

if [ ! -f "pyproject.toml" ]; then
    echo ""
    echo "=========================================="
    echo "请选择代码上传方式:"
    echo ""
    echo "方式1 - 从本地 scp 上传（推荐）"
    echo "  在本地执行:"
    echo "  cd /Users/blazethan/Projects/OCR_seed_audit"
    echo "  tar czf seed-scanner.tar.gz --exclude='.venv' --exclude='output' --exclude='.git' ."
    echo "  scp seed-scanner.tar.gz root@<服务器IP>:$INSTALL_DIR/"
    echo ""
    echo "方式2 - 从 Git 仓库克隆"
    echo "  git clone <你的私有仓库> $INSTALL_DIR"
    echo ""
    echo "=========================================="
    echo ""
    read -rp "上传完成后按 Enter 继续..."

    if [ -f "seed-scanner.tar.gz" ]; then
        echo "解压上传的代码..."
        tar xzf seed-scanner.tar.gz
        rm seed-scanner.tar.gz
        echo "✓ 代码解压完成"
    fi

    if [ ! -f "pyproject.toml" ]; then
        echo "错误: 未找到项目代码"
        exit 1
    fi
else
    echo "✓ 项目代码已存在"
fi

# 5. 创建必要的目录
echo ""
echo "[5/7] 创建目录结构..."
mkdir -p output data
chmod 755 output data

# 6. 构建 Docker 镜像
echo ""
echo "[6/7] 构建 Docker 镜像..."
docker build -f Dockerfile.slim -t seed-scanner:latest . 2>&1 | tee build.log

echo ""
echo "✓ 镜像构建成功"

# 7. 配置 SMB 挂载
echo ""
echo "[7/7] 配置 SMB 挂载..."

mkdir -p "$SMB_MOUNT"

if ! mountpoint -q "$SMB_MOUNT" 2>/dev/null; then
    if ! grep -q "$SMB_MOUNT" /etc/fstab; then
        echo ""
        read -rp "SMB 服务器 IP: " SMB_SERVER
        read -rp "SMB 共享名称: " SMB_SHARE
        read -rp "SMB 用户名: " SMB_USER
        read -rsp "SMB 密码: " SMB_PASS
        echo ""

        # 创建凭证文件
        CRED_FILE="/root/.smbcredentials-${SMB_SHARE}"
        echo "username=$SMB_USER" > "$CRED_FILE"
        echo "password=$SMB_PASS" >> "$CRED_FILE"
        chmod 600 "$CRED_FILE"

        # 添加到 fstab
        echo "//$SMB_SERVER/$SMB_SHARE $SMB_MOUNT cifs credentials=$CRED_FILE,iocharset=utf8,vers=3.0,_netdev 0 0" >> /etc/fstab
    fi

    mount -a || true

    if mountpoint -q "$SMB_MOUNT"; then
        echo "✓ SMB 挂载成功"
    else
        echo "⚠ SMB 挂载失败，请稍后手动配置"
    fi
else
    echo "✓ SMB 已挂载"
fi

# 8. 创建 systemd 服务
echo ""
echo "创建服务..."

SERVICE_NAME="seed-scanner-$(basename "$INSTALL_DIR")"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=Seed Scanner - $INSTALL_DIR
After=network.target docker.service

[Service]
Type=oneshot
WorkingDirectory=$INSTALL_DIR

ExecStartPre=-/bin/mountpoint -q $SMB_MOUNT || /bin/mount -a

ExecStart=/usr/bin/docker run --rm \\
    --name ${SERVICE_NAME}-run \\
    -v $SMB_MOUNT:/scan:ro \\
    -v $INSTALL_DIR/output:/app/output \\
    -v $INSTALL_DIR/data:/app/data \\
    -v $INSTALL_DIR/config.yaml:/app/config.yaml:ro \\
    -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \\
    -e TZ=Asia/Shanghai \\
    seed-scanner:latest \\
    /scan --config /app/config.yaml

ExecStopPost=-/usr/bin/docker rm -f ${SERVICE_NAME}-run 2>/dev/null || true

[Install]
WantedBy=multi-user.target
EOF

cat > "/etc/systemd/system/${SERVICE_NAME}.timer" << EOF
[Unit]
Description=Run Seed Scanner ($INSTALL_DIR) every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.timer"
systemctl start "${SERVICE_NAME}.timer"

# 创建快捷脚本
SCAN_CMD="/usr/local/bin/seed-scan-$(basename "$INSTALL_DIR")"
cat > "$SCAN_CMD" << EOF
#!/bin/bash
cd $INSTALL_DIR
if ! mountpoint -q $SMB_MOUNT; then
    mount -a || { echo "SMB 挂载失败"; exit 1; }
fi
docker run --rm \\
    -v $SMB_MOUNT:/scan:ro \\
    -v $INSTALL_DIR/output:/app/output \\
    -v $INSTALL_DIR/data:/app/data \\
    -v $INSTALL_DIR/config.yaml:/app/config.yaml:ro \\
    -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \\
    seed-scanner:latest \\
    /scan \\"\$@\"
EOF
chmod +x "$SCAN_CMD"

echo ""
echo "=========================================="
echo "✓ 部署完成!"
echo "=========================================="
echo ""
echo "安装目录: $INSTALL_DIR"
echo "SMB挂载:  $SMB_MOUNT"
echo "服务名:   $SERVICE_NAME"
echo ""
echo "快捷命令: $SCAN_CMD"
echo ""
echo "查看状态: systemctl status ${SERVICE_NAME}.timer"
echo "立即扫描: $SCAN_CMD"
echo "查看日志: journalctl -u ${SERVICE_NAME}.service -f"
echo ""
