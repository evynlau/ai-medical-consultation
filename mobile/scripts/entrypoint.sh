#!/bin/bash
# ============================================================
# 容器内 entrypoint - 编译 uni-app Android APK
# ============================================================
set -e

# 加载 JAVA_HOME(从镜像 /etc/profile.d/java.sh)
. /etc/profile.d/java.sh 2>/dev/null || true

echo "==============================================="
echo "  uni-app Android APK 离线打包"
echo "==============================================="
echo "  Node:     $(node -v)"
echo "  Java:     $(java -version 2>&1 | head -1)"
echo "  JAVA_HOME: $JAVA_HOME"
echo "  Gradle:   $(gradle --version 2>/dev/null | grep '^Gradle' | head -1)"
echo "  Android:  $ANDROID_HOME"
echo "==============================================="

# 1. 把 src/manifest.json 的 appid 替换成正确的(打包需要)
#    用户在主机上 build 时应已经填好,这里只是校验
APPID=$(grep '"appid"' src/manifest.json | head -1 | sed -E 's/.*"appid":\s*"([^"]+)".*/\1/')
if [ -z "$APPID" ] || [ "$APPID" = "__UNI__XXXXXXX" ]; then
    echo "⚠️  警告: src/manifest.json 的 appid 还是占位的 __UNI__XXXXXXX"
    echo "    打包出来的 APK 包名会乱码,建议先填上真实 DCloud AppID"
    echo ""
fi

# 2. 编译 uni-app 到 Android 工程
echo ""
echo ">>> 1/3 编译 uni-app (app-android)..."
npm run build:app-android 2>&1 | tail -30

# 3. 检查产物
APP_DIR="unpackage/dist/build/app-android"
if [ ! -d "$APP_DIR" ]; then
    echo "❌ 编译失败:$APP_DIR 不存在"
    exit 1
fi

# 4. 用 gradle 编译 APK
echo ""
echo ">>> 2/3 Gradle 编译 APK..."
cd "$APP_DIR"

# 注入 local.properties(SDK 路径)
echo "sdk.dir=$ANDROID_HOME" > local.properties

# 编译(第一次会下 200MB+ 依赖,耐心等)
echo "    (首次构建会下载 Gradle 依赖,大约 5-10 分钟)"
gradle assembleDebug --no-daemon 2>&1 | tail -40

# 5. 找 APK
echo ""
echo ">>> 3/3 查找 APK 产物..."
APK_PATH=$(find . -name "*.apk" -type f | head -1)
if [ -z "$APK_PATH" ]; then
    echo "❌ 没找到 APK"
    exit 1
fi

# 6. 复制到 /build/output 方便主机挂载
mkdir -p /build/output
cp "$APK_PATH" /build/output/ai-doctor.apk
SIZE=$(du -h /build/output/ai-doctor.apk | cut -f1)

echo ""
echo "==============================================="
echo "✅ 打包成功!"
echo "   APK 路径: /build/output/ai-doctor.apk"
echo "   APK 大小: $SIZE"
echo ""
echo "   安装到手机:"
echo "     adb install /build/output/ai-doctor.apk"
echo "   或传到手机文件管理器点击安装"
echo "==============================================="
