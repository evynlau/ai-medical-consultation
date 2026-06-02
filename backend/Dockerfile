FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 数据目录
RUN mkdir -p data/faiss_index

EXPOSE 8000

# 默认启动:初始化 KB + 启动服务
CMD ["sh", "-c", "python -c 'import sys; sys.path.insert(0, \".\"); from scripts.init_kb import main' 2>/dev/null || true; uvicorn main:app --host 0.0.0.0 --port 8000"]
