#!/bin/bash
# Build and push seed-scanner image to Docker Hub

set -e

# 配置
IMAGE_NAME="seed-scanner"
DOCKERHUB_USER="your-dockerhub-username"  # 修改为你的 Docker Hub 用户名
VERSION=$(grep -E '^version\s*=' pyproject.toml | sed 's/.*=\s*"\(.*\)".*/\1/')

echo "=========================================="
echo "  Seed Scanner Docker 构建脚本"
echo "=========================================="
echo ""
echo "镜像名称: $IMAGE_NAME"
echo "版本: $VERSION"
echo "Docker Hub: $DOCKERHUB_USER/$IMAGE_NAME"
echo ""

# 检查 Docker 是否可用
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

# 检查是否登录 Docker Hub
if ! docker info | grep -q "Username"; then
    echo "请先登录 Docker Hub:"
    echo "  docker login"
    exit 1
fi

# 获取当前登录的用户名
CURRENT_USER=$(docker info 2>/dev/null | grep Username | awk '{print $2}')
if [ -n "$CURRENT_USER" ] && [ "$CURRENT_USER" != "$DOCKERHUB_USER" ]; then
    echo "检测到已登录用户: $CURRENT_USER"
    read -p "使用当前用户 ($CURRENT_USER) 还是配置中的用户 ($DOCKERHUB_USER)? [current/config] " choice
    if [ "$choice" = "current" ]; then
        DOCKERHUB_USER=$CURRENT_USER
    fi
fi

echo "开始构建镜像..."
echo ""

# 构建镜像
docker build \
    --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
    --build-arg VERSION=$VERSION \
    -t $IMAGE_NAME:latest \
    -t $IMAGE_NAME:$VERSION \
    .

echo ""
echo "✓ 镜像构建完成"
echo ""

# 标记镜像
echo "标记镜像..."
docker tag $IMAGE_NAME:latest $DOCKERHUB_USER/$IMAGE_NAME:latest
docker tag $IMAGE_NAME:$VERSION $DOCKERHUB_USER/$IMAGE_NAME:$VERSION

# 推送到 Docker Hub
echo ""
echo "推送到 Docker Hub ($DOCKERHUB_USER)..."
docker push $DOCKERHUB_USER/$IMAGE_NAME:latest
docker push $DOCKERHUB_USER/$IMAGE_NAME:$VERSION

echo ""
echo "=========================================="
echo "✓ 推送完成!"
echo "=========================================="
echo ""
echo "镜像地址:"
echo "  $DOCKERHUB_USER/$IMAGE_NAME:latest"
echo "  $DOCKERHUB_USER/$IMAGE_NAME:$VERSION"
echo ""
echo "服务器使用:"
echo "  docker pull $DOCKERHUB_USER/$IMAGE_NAME:latest"
echo ""
