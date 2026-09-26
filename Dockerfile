# ========== 阶段一：构建前端 ==========
FROM node:20-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ========== 阶段二：运行镜像 ==========
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    DRAWCODE_DATA_DIR=/app/data \
    DRAWCODE_PORT=9862 \
    TZ=Asia/Shanghai

# 中文字体（微信图文封面 1068x455 生成需要）
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY main.py ./
COPY ceec.png ./
COPY --from=frontend /build/dist ./frontend/dist

RUN mkdir -p /app/data
VOLUME ["/app/data"]
EXPOSE 9862

CMD ["python", "main.py"]
