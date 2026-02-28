#!/bin/bash
# 构建 seed-scanner 镜像并导出（私有项目使用）

set -e

IMAGE_NAME="seed-scanner"
VERSION=$(grep -E '^version\s*=' pyproject.toml | sed 's/.*=\s*"\(.*\)".*/\1/')
OUTPUT_FILE="${IMAGE_NAME}-${VERSION}.tar"

echo "=========================================="
echo "  Seed Scanner 私有镜像构建"
echo "=========================================="
echo ""
echo "镜像名称: $IMAGE_NAME"
echo "版本: $VERSION"
echo ""

# 检查 Docker
if ! command -v docker &> /dev/null; then
    echo "错误: Docker 未安装"
    exit 1
fi

echo "[1/3] 构建镜像..."
docker build -f Dockerfile.slim -t $IMAGE_NAME:latest -t $IMAGE_NAME:$VERSION .

echo ""
echo "[2/3] 导出镜像..."
docker save -o $OUTPUT_FILE $IMAGE_NAME:latest $IMAGE_NAME:$VERSION

echo ""
echo "[3/3] 压缩镜像..."
gzip -f $OUTPUT_FILE
OUTPUT_FILE="${OUTPUT_FILE}.gz"

echo ""
echo "=========================================="
echo "✓ 构建完成!"
echo "=========================================="
echo ""
echo "镜像文件: $OUTPUT_FILE"
echo "文件大小: $(du -h $OUTPUT_FILE | cut -f1)"
echo ""
echo "传输到服务器:"
echo "  scp $OUTPUT_FILE user@server:/opt/seed-scanner/"
echo ""
echo "服务器导入:"
echo "  gunzip $OUTPUT_FILE"
echo "  docker load -i ${IMAGE_NAME}-${VERSION}.tar"
echo ""
