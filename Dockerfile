# ==============================================================================
# Stage 1: Builder - 构建依赖
# ==============================================================================
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /build

# 安装构建依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 构建工具
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir hatchling

# 复制项目配置文件
COPY pyproject.toml README.md ./

# 复制源代码
COPY src/ src/

# 构建 wheel 包
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels .

# ==============================================================================
# Stage 2: Runtime - 运行时环境
# ==============================================================================
FROM python:3.11-slim AS runtime

# 创建非 root 用户
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1001 appuser

# 设置工作目录
WORKDIR /app

# 从 builder 阶段复制 wheel 包
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/src /app/src

# 安装应用（仅运行时依赖）
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-index --find-links=/wheels naver-dict-mcp && \
    rm -rf /wheels

# 切换到非 root 用户
RUN chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5.0)" || exit 1

# 暴露端口
EXPOSE 8000

# 设置环境变量
ENV SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8000 \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1

# 运行服务器
CMD ["python", "src/server.py"]
