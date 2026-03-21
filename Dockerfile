# TCB 部署用 Dockerfile
# 同时构建前端和后端

FROM python:3.11-slim AS backend-builder

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc libffi-dev ffmpeg nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# 安装后端依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 3 --timeout 60 -r requirements.txt

# 安装 spacy 模型
COPY en_core_web_lg-3.8.0-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir /tmp/en_core_web_lg-3.8.0-py3-none-any.whl \
    && rm /tmp/en_core_web_lg-3.8.0-py3-none-any.whl

# ========== 前端构建阶段 ==========
FROM node:20-slim AS frontend-builder

WORKDIR /app
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm install

COPY src/frontend/ ./
RUN npm run build

# ========== 最终镜像 ==========
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 复制后端 Python 包
COPY --from=backend-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend-builder /usr/local/bin /usr/local/bin

# 复制后端文件
COPY requirements.txt .
COPY src/interview/ ./src/interview/
COPY migrations/ ./migrations/

# 复制前端构建产物
COPY --from=frontend-builder /app/dist ./src/frontend/dist

# 创建 uploads 目录
RUN mkdir -p /app/uploads

EXPOSE 8001

# 启动后端（前端静态文件由 FastAPI 托管）
CMD ["uvicorn", "src.interview.main:app", "--host", "0.0.0.0", "--port", "8001"]