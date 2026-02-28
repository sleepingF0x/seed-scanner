#!/bin/bash
# Ubuntu Docker 部署脚本
# 使用方法: curl -fsSL https://your-domain/deploy.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_NAME="seed-scanner"
INSTALL_DIR="/opt/$PROJECT_NAME"
SMB_MOUNT_POINT="/mnt/xspt"

print_header() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Seed Scanner Ubuntu Docker 部署${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}[步骤]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[成功]${NC} $1"
}

print_error() {
    echo -e "${RED}[错误]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

# 检查 root 权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        print_error "请使用 sudo 运行此脚本"
        exit 1
    fi
}

# 安装 Docker
install_docker() {
    print_step "检查 Docker 安装..."
    if command -v docker &> /dev/null; then
        print_success "Docker 已安装 ($(docker --version))"
    else
        print_step "安装 Docker..."
        curl -fsSL https://get.docker.com | sh
        systemctl enable docker
        systemctl start docker
        print_success "Docker 安装完成"
    fi

    # 检查 Docker Compose
    if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
        print_success "Docker Compose 已安装"
    else
        print_step "安装 Docker Compose..."
        apt-get update && apt-get install -y docker-compose-plugin
        print_success "Docker Compose 安装完成"
    fi
}

# 配置 SMB 挂载
setup_smb() {
    print_step "配置 SMB 挂载..."

    # 安装 cifs-utils
    apt-get install -y cifs-utils

    # 创建挂载点
    mkdir -p $SMB_MOUNT_POINT

    # 检查是否已挂载
    if mount | grep -q "$SMB_MOUNT_POINT"; then
        print_success "SMB 已挂载到 $SMB_MOUNT_POINT"
        return
    fi

    # 获取 SMB 信息
    echo ""
    echo "请提供 SMB 共享信息:"
    read -p "SMB 服务器地址 (如: 192.168.1.100): " smb_server
    read -p "共享名称 (如: share): " smb_share
    read -p "用户名: " smb_user
    read -s -p "密码: " smb_pass
    echo ""

    # 创建凭据文件
    cat > /root/.smbcredentials << EOF
username=$smb_user
password=$smb_pass
EOF
    chmod 600 /root/.smbcredentials

    # 测试挂载
    print_step "测试 SMB 挂载..."
    mount -t cifs //${smb_server}/${smb_share} ${SMB_MOUNT_POINT} \
        -o credentials=/root/.smbcredentials,charset=utf-8,uid=root,gid=root,file_mode=0777,dir_mode=0777

    if mount | grep -q "$SMB_MOUNT_POINT"; then
        print_success "SMB 挂载成功"
        # 添加到 fstab 实现开机自动挂载
        echo "//${smb_server}/${smb_share} ${SMB_MOUNT_POINT} cifs credentials=/root/.smbcredentials,charset=utf-8,uid=root,gid=root,file_mode=0777,dir_mode=0777 0 0" >> /etc/fstab
    else
        print_error "SMB 挂载失败"
        exit 1
    fi
}

# 创建项目目录
setup_project() {
    print_step "创建项目目录..."
    mkdir -p $INSTALL_DIR
    cd $INSTALL_DIR

    # 创建必要的子目录
    mkdir -p output data

    print_success "项目目录: $INSTALL_DIR"
}

# 创建配置文件
create_config() {
    print_step "创建配置文件..."

    cat > $INSTALL_DIR/config.yaml << 'EOF'
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
  smtp_server: "smtp.qq.com"
  smtp_port: 587
  username: "your_email@qq.com"
  password: "your_auth_code"
  to_address: "recipient@example.com"
  subject: "助记词扫描结果 / Seed Scanner Report"

output:
  directory: "./output"
  generate_json: true
  generate_txt: true

database:
  path: "./data/seed_scanner.db"
EOF

    print_success "配置文件已创建: $INSTALL_DIR/config.yaml"
    print_warning "请根据需要编辑配置文件 (尤其是邮件设置)"
}

# 创建 Dockerfile
create_dockerfile() {
    print_step "创建 Dockerfile..."

    cat > $INSTALL_DIR/Dockerfile << 'EOF'
FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 libgl1-mesa-glx \
    wget curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY data/ ./data/

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.cargo/bin/uv /usr/local/bin/uv && \
    uv sync --no-dev --no-cache

RUN mkdir -p output data models

ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PADDLE_PDX_MODEL_ROOT=/app/models
ENV PYTHONUNBUFFERED=1
ENV TZ=Asia/Shanghai

RUN python -c "from paddleocr import PaddleOCR; PaddleOCR()" 2>/dev/null || true

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

ENTRYPOINT ["uv", "run", "python", "-m", "src.main"]
CMD ["--help"]
EOF

    print_success "Dockerfile 已创建"
}

# 创建 docker-compose.yml
create_compose() {
    print_step "创建 docker-compose.yml..."

    cat > $INSTALL_DIR/docker-compose.yml << EOF
version: '3.8'

services:
  seed-scanner:
    build:
      context: .
      dockerfile: Dockerfile
    image: seed-scanner:latest
    container_name: seed-scanner
    volumes:
      # SMB 挂载的主机目录映射到容器
      - ${SMB_MOUNT_POINT}:/scan:ro
      # 输出目录
      - ./output:/app/output
      # 数据库持久化
      - ./data:/app/data
      # 配置文件
      - ./config.yaml:/app/config.yaml:ro
      # 模型缓存（避免重复下载）
      - ./models:/app/models
    environment:
      - PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
      - PADDLE_PDX_MODEL_ROOT=/app/models
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
    command: ["/scan", "--config", "/app/config.yaml"]
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 2G

  # 可选：定时任务服务
  seed-scanner-cron:
    build:
      context: .
      dockerfile: Dockerfile
    image: seed-scanner:latest
    container_name: seed-scanner-cron
    volumes:
      - ${SMB_MOUNT_POINT}:/scan:ro
      - ./output:/app/output
      - ./data:/app/data
      - ./config.yaml:/app/config.yaml:ro
      - ./models:/app/models
    environment:
      - PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
      - PADDLE_PDX_MODEL_ROOT=/app/models
      - TZ=Asia/Shanghai
    # 使用 ofelia 作为定时任务调度器
    command: >
      sh -c "echo '0 6 * * * /usr/local/bin/uv run python -m src.main /scan --config /app/config.yaml >> /app/output/cron.log 2>&1' | crontab - && cron -f"
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
    profiles:
      - cron  # 默认不启动，使用 --profile cron 启动
EOF

    print_success "docker-compose.yml 已创建"
}

# 创建管理脚本
create_manage_script() {
    print_step "创建管理脚本..."

    cat > $INSTALL_DIR/seed-scanner.sh << 'EOF'
#!/bin/bash
# Seed Scanner 管理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

show_help() {
    echo "Seed Scanner 管理脚本"
    echo ""
    echo "用法: ./seed-scanner.sh [命令]"
    echo ""
    echo "命令:"
    echo "  build       构建 Docker 镜像"
    echo "  scan        运行扫描"
    echo "  scan-force  强制重新扫描"
    echo "  logs        查看日志"
    echo "  status      查看状态"
    echo "  stop        停止服务"
    echo "  shell       进入容器 Shell"
    echo "  update      更新代码并重建"
    echo "  clean       清理数据库和输出"
    echo "  help        显示帮助"
}

case "$1" in
    build)
        echo "构建 Docker 镜像..."
        docker-compose build
        ;;
    scan)
        echo "运行扫描..."
        docker-compose up --abort-on-container-exit
        ;;
    scan-force)
        echo "强制重新扫描..."
        docker-compose run --rm seed-scanner /scan --config /app/config.yaml --force
        ;;
    logs)
        docker-compose logs -f
        ;;
    status)
        echo "容器状态:"
        docker-compose ps
        echo ""
        echo "最近扫描结果:"
        ls -lt output/ 2>/dev/null | head -5
        ;;
    stop)
        docker-compose down
        ;;
    shell)
        docker-compose run --rm seed-scanner sh
        ;;
    update)
        echo "更新项目..."
        git pull
        docker-compose build --no-cache
        ;;
    clean)
        read -p "确定要清理所有数据吗? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            docker-compose down
            rm -rf output/* data/*.db
            echo "已清理"
        fi
        ;;
    help|*)
        show_help
        ;;
esac
EOF

    chmod +x $INSTALL_DIR/seed-scanner.sh
    print_success "管理脚本已创建: $INSTALL_DIR/seed-scanner.sh"
}

# 构建镜像
build_image() {
    print_step "构建 Docker 镜像..."
    cd $INSTALL_DIR
    docker-compose build
    print_success "镜像构建完成"
}

# 测试运行
test_run() {
    print_step "测试运行..."
    cd $INSTALL_DIR
    docker-compose run --rm seed-scanner --help
    print_success "测试完成"
}

# 创建 systemd 服务
create_systemd_service() {
    print_step "创建 systemd 服务..."

    cat > /etc/systemd/system/seed-scanner.service << EOF
[Unit]
Description=Seed Scanner Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
WorkingDirectory=${INSTALL_DIR}
ExecStart=${INSTALL_DIR}/seed-scanner.sh scan
User=root
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    cat > /etc/systemd/system/seed-scanner.timer << EOF
[Unit]
Description=Run Seed Scanner every 6 hours
Requires=docker.service

[Timer]
OnCalendar=*-*-* 00,06,12,18:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload
    print_success "systemd 服务已创建"
    print_warning "启用定时任务: systemctl enable --now seed-scanner.timer"
}

# 显示完成信息
show_finish() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}    部署完成!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "安装目录: $INSTALL_DIR"
    echo "SMB 挂载: $SMB_MOUNT_POINT"
    echo ""
    echo "常用命令:"
    echo "  cd $INSTALL_DIR"
    echo "  ./seed-scanner.sh build    # 构建镜像"
    echo "  ./seed-scanner.sh scan     # 运行扫描"
    echo "  ./seed-scanner.sh logs     # 查看日志"
    echo "  ./seed-scanner.sh status   # 查看状态"
    echo ""
    echo "手动运行:"
    echo "  docker-compose up"
    echo ""
    echo "定时任务:"
    echo "  systemctl enable --now seed-scanner.timer"
    echo ""
}

# 主函数
main() {
    print_header
    check_root
    install_docker
    setup_smb
    setup_project
    create_config
    create_dockerfile
    create_compose
    create_manage_script
    build_image
    test_run
    create_systemd_service
    show_finish
}

# 运行
main
