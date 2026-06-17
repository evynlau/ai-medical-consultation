# 打包 APK 步骤

> 目标:把 `mobile/` 项目打包成 Android APK,在真机/模拟器上安装测试。

## 0. 选择打包方式(根据你本机环境)

| 你的环境 | 推荐方式 | 难度 |
|---------|---------|------|
| **Linux + Docker** | **方式 B(本文档主推)** | ⭐ 最简单 |
| **Linux,无 Docker,有 Java** | 方式 C:CLI 离线打包 | ⭐⭐ |
| **Windows / Mac** | 方式 A:HBuilderX | ⭐ 最简单 |

---

## 方式 B:Linux + Docker 离线打包(本文档主推)

**优势**:一行命令,本机不需要 HBuilderX/Java/Android SDK,环境全在 Docker 镜像里。

### 一次性准备
```bash
# 装 Docker(没装的话)
sudo apt install docker.io
sudo systemctl start docker
sudo usermod -aG docker $USER  # 可选,避免每次 sudo
# 注销重登后生效,或:newgrp docker
```

### 编译 APK
```bash
cd mobile
./scripts/build-apk.sh
```

**首次构建**:
- 下载 Java 17 镜像 + Android SDK (~500MB) + Gradle 8.2 + npm 依赖
- 编译 uni-app 到原生 Android 工程
- Gradle 编译 APK(下载 Maven 依赖约 200MB)
- **总耗时 10-15 分钟**

**二次构建**:
- 复用镜像缓存,只重新编译你改的代码
- **总耗时 1-2 分钟**

### 产物位置
```
mobile/output/ai-doctor.apk
```

### 安装到手机
```bash
# USB 调试 + adb
adb install -r mobile/output/ai-doctor.apk

# 或用文件管理器:把 apk 传到手机,点击安装
```

### 常用命令
```bash
# 强制重建镜像(代码改 Dockerfile 了才用)
docker build --no-cache -t ai-doctor-builder mobile/

# 看构建日志(失败时)
./scripts/build-apk.sh 2>&1 | tee build.log

# 删掉旧镜像,释放空间
docker rmi ai-doctor-builder
```

### 排错

**`docker: command not found`**
→ 装 Docker:`sudo apt install docker.io`

**`Cannot connect to the Docker daemon`**
→ 启动 daemon:`sudo systemctl start docker`

**`gradle assembleDebug` 失败 / 下载慢**
→ 第一次需要下 Maven 依赖,翻墙环境配个代理:
```bash
mkdir -p ~/.gradle
cat > ~/.gradle/init.gradle <<'EOF'
allprojects {
    repositories {
        maven { url 'https://maven.aliyun.com/repository/public' }
        maven { url 'https://maven.aliyun.com/repository/google' }
    }
}
EOF
```

**`SDK location not found`**
→ 镜像内已自动配置 `local.properties`,如果还报,清空缓存重建:
```bash
docker build --no-cache -t ai-doctor-builder .
```

---

## 方式 A:Windows/Mac 用 HBuilderX 云打包

### 一次性准备
1. 下载 [HBuilderX 标准版](https://www.dcloud.io/hbuilderx.html)(免费)
2. 打开 HBuilderX → 右上角登录 → 注册(https://dev.dcloud.net.cn/)
3. 实名认证(打 Release 包必须)
4. 应用列表 → 新建应用 → 名字"AI 家庭医生" → 类型 Android
5. 拿到 AppID(格式 `__UNI__XXXXXXX`),填到 `mobile/src/manifest.json` 第 3 行

### 配置后端地址
打开 `mobile/src/api/index.js`,根据场景改 `BASE_URL`:
| 场景 | URL |
|------|-----|
| Android 模拟器 | `http://10.0.2.2:8000/api/v1` |
| 真机 + 电脑同 WiFi | `http://192.168.x.x:8000/api/v1` |
| 生产 | `https://api.your-domain.com/api/v1` |

### 启动后端
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### HBuilderX 打开项目
1. 文件 → 打开目录 → 选 `mobile/`(不是 `mobile/src/`)
2. 右键 `manifest.json` → 源码视图,确认 appid 已填

### 调试(可选,推荐)
- 装 Android Studio 模拟器 或夜神/雷电模拟器
- HBuilderX → 运行 → 运行到手机或模拟器 → Android App-基座
- 真机:USB 调试,USB 连电脑

### 云打包
1. 菜单 → 发行 → 原生 APP-云打包
2. 选 Android → 证书选"使用 DCloud 公测证书" → 点打包
3. 等 3-5 分钟,弹框显示 APK 下载链接
4. 下载安装

---

## 方式 C:Linux CLI 离线打包(没 Docker 时用)

需要本机装 Java 17 + Android SDK,首次配置 30-60 分钟。

```bash
# 1. 装 Java 17
sudo apt install openjdk-17-jdk

# 2. 装 Android SDK
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
mkdir -p ~/android-sdk/cmdline-tools
unzip commandlinetools-linux-11076708_latest.zip -d ~/android-sdk/cmdline-tools
mv ~/android-sdk/cmdline-tools/cmdline-tools ~/android-sdk/cmdline-tools/latest
export ANDROID_HOME=~/android-sdk
export PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin

# 3. 装 SDK 组件
yes | sdkmanager --licenses
sdkmanager "platform-tools" "platforms;android-30" "build-tools;30.0.3"

# 4. 编译
cd mobile
export ANDROID_HOME=~/android-sdk
npm install
npm run build:app-android
cd unpackage/dist/build/app-android
echo "sdk.dir=$ANDROID_HOME" > local.properties
gradle assembleDebug

# 5. APK 在 app-android/app/build/outputs/apk/debug/
```

---

## 通用:包名 / 图标 / 启动图

不管用哪种方式,都改这些文件:

| 资源 | 位置 | 怎么改 |
|------|------|--------|
| 包名 / AppID | `src/manifest.json` 的 `appid` | HBuilderX 申请的 AppID |
| 应用名 | `src/manifest.json` 的 `name` | 任意字符串 |
| tabBar 图标 | `src/static/tabbar/*.png` | 81x81 黑白 PNG,4 主 + 4 激活态 |
| 应用图标 | `src/static/icons/app.png` | 200x200,打包时自动多分辨率 |
| 启动图 | `src/static/logo.png` | 1024x1024 |
| 后端地址 | `src/api/index.js` 顶部 `BASE_URL` | 见各方式说明 |

---

## 常见问题

### App 安装后白屏
- 检查后端地址(`uni.request` 报错会进 onShow 看到)
- 真机调试建议先 USB 调试跑基座,看 HBuilderX 控制台
- 装 vconsole 调试:
```js
// src/main.js 顶部加
if (process.env.NODE_ENV !== 'production') {
  const VConsole = require('vconsole')
  new VConsole()
}
```

### 接口 401
- 后端默认账号 admin/admin(具体看 `backend/scripts/seed.py`)

### 真机访问不到后端
- 电脑手机同 WiFi,后端用 `--host 0.0.0.0`
- BASE_URL 用电脑局域网 IP,不是 localhost

打包遇到任何问题把日志贴给我,我帮你看。