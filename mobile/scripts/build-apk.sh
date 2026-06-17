#!/bin/bash
# ============================================================
# 一行命令本地出 APK
# 用法: ./scripts/build-apk.sh
# 首次构建约 10-15 分钟(下载 SDK/Gradle 依赖)
# 二次构建约 1-2 分钟
# ============================================================
set -e

cd "$(dirname "$0")/.."

echo ">>> 检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ 找不到 docker,请先安装 Docker"
    echo "   Linux: sudo apt install docker.io"
    exit 1
fi

# 检查 docker daemon 是否运行
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon 未运行,启动一下:"
    echo "   sudo systemctl start docker"
    exit 1
fi

# 镜像名
IMAGE_NAME="ai-doctor-builder"

# 是否需要重新构建镜像(代码改了就 rebuild)
echo ""
echo ">>> 检查镜像..."
if ! docker image inspect "$IMAGE_NAME" &> /dev/null; then
    echo "    首次构建,需要下载 SDK + Gradle + npm 包,约 10-15 分钟"
    echo ""
    docker build -t "$IMAGE_NAME" .
else
    echo "    镜像已存在,直接复用(增量构建,约 1-2 分钟)"
fi

# 运行容器
echo ""
echo ">>> 启动容器编译..."
echo "    (编译日志会实时输出,首次较慢请耐心等待)"
echo ""

docker run --rm \
    -v "$(pwd)/output:/build/output" \
    "$IMAGE_NAME" build

echo ""
echo "==============================================="
echo "✅ 完成!"
echo "   APK: $(pwd)/output/ai-doctor.apk"
echo "==============================================="
