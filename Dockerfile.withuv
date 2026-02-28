# Seed Scanner Docker Image
FROM python:3.12-slim-bookworm

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-0 \
    libgl1-mesa-glx \
    wget \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 先复制依赖文件（利用 Docker 缓存层）
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY data/ ./data/

# 安装 uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.cargo/bin/uv /usr/local/bin/uv

# 安装 Python 依赖
RUN uv sync --no-dev --no-cache

# 创建必要的目录
RUN mkdir -p output data

# 预下载 PaddleOCR 模型（避免运行时下载）
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
ENV PADDLE_PDX_MODEL_ROOT=/app/models
RUN mkdir -p /app/models && \
    python -c "from paddleocr import PaddleOCR; PaddleOCR()" 2>/dev/null || true

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV TZ=Asia/Shanghai

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 设置入口点
ENTRYPOINT ["uv", "run", "python", "-m", "src.main"]
CMD ["--help"]
