# Seed Scanner Docker Image - 不依赖 uv
FROM python:3.12-slim-bookworm

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
COPY data/ ./data/

# 用 uv 安装依赖（构建阶段使用，不保留在最终镜像）
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.cargo/bin/uv export --no-dev --no-hashes -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cargo /root/.cache /requirements.txt

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

# 直接用 Python 运行（不依赖 uv）
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]
