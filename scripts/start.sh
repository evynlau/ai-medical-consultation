#!/usr/bin/env bash
# 一键启动脚本(Mac/Linux)
# 启动后端 + 前端开发服务器

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==========================================="
echo "  AI 智能问诊系统 - 启动"
echo "==========================================="

# 1. 检查环境
echo ""
echo "[1/5] 检查环境..."
if ! command -v python3 &> /dev/null; then
  echo "❌ 未找到 python3,请先安装 Python 3.10+"
  exit 1
fi
if ! command -v node &> /dev/null; then
  echo "❌ 未找到 node,请先安装 Node.js 18+"
  exit 1
fi

# 2. 准备后端
echo ""
echo "[2/5] 准备后端..."
cd "$ROOT/backend"
if [ ! -d "venv" ]; then
  echo "  · 创建 Python 虚拟环境..."
  python3 -m venv venv
fi
source venv/bin/activate

if [ ! -f ".env" ]; then
  echo "  · 创建 .env 配置文件..."
  cp .env.example .env
fi

echo "  · 安装 Python 依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# 3. 初始化知识库
echo ""
echo "[3/5] 初始化知识库..."
mkdir -p data/faiss_index
python ../scripts/init_kb.py

# 4. 启动后端
echo ""
echo "[4/5] 启动后端服务 (http://localhost:8000)..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
sleep 3

# 5. 启动前端
echo ""
echo "[5/5] 启动前端开发服务 (http://localhost:5173)..."
cd "$ROOT/frontend"
if [ ! -d "node_modules" ]; then
  echo "  · 安装前端依赖..."
  npm install
fi
npm run dev

# 退出时关闭后端
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT
