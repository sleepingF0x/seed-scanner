#!/bin/bash
# Seed Scanner 一键扫描脚本

TARGET="/Volumes/xspt"
LOG_DIR="output"
LOG_FILE="$LOG_DIR/scan_$(date +%Y%m%d_%H%M%S).log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}    Seed Scanner 启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "扫描目标: $TARGET"
echo "日志文件: $LOG_FILE"
echo ""

# 检查 SMB 挂载
if [ ! -d "$TARGET" ]; then
    echo -e "${RED}错误: SMB 目录未挂载 $TARGET${NC}"
    exit 1
fi

# 检查目录可读
if [ ! -r "$TARGET" ]; then
    echo -e "${RED}错误: 无法读取目录 $TARGET${NC}"
    exit 1
fi

# 统计文件数量
echo -e "${YELLOW}正在统计图片文件...${NC}"
IMG_COUNT=$(find "$TARGET" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.bmp" -o -name "*.webp" \) 2>/dev/null | wc -l)
echo "找到 $IMG_COUNT 个图片文件"
echo ""

# 确认扫描
if [ "$IMG_COUNT" -gt 1000 ]; then
    echo -e "${YELLOW}警告: 图片数量较多 ($IMG_COUNT)，扫描可能需要较长时间${NC}"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "已取消"
        exit 0
    fi
fi

# 运行扫描
echo -e "${GREEN}开始扫描...${NC}"
uv run python -m src.main "$TARGET" --config config.yaml 2>&1 | tee "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo -e "${GREEN}========================================${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}扫描完成!${NC}"
else
    echo -e "${RED}扫描退出，代码: $EXIT_CODE${NC}"
fi
echo "结果保存在 output/ 目录"
echo -e "${GREEN}========================================${NC}"
