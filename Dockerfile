# Seed Scanner Docker Image - Pure pip, no uv
FROM python:3.12-slim-bookworm

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY pyproject.toml ./
COPY src/ ./src/
COPY data/ ./data/

# 安装 Python 依赖（直接用 pip，不依赖 uv）
RUN pip install --no-cache-dir \
    paddlepaddle \
    paddleocr \
    pillow \
    imagehash \
    pyyaml

# 创建必要的目录
RUN mkdir -p output data

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV TZ=Asia/Shanghai

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 直接用 Python 运行
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]
