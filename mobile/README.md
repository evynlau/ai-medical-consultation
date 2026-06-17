# AI 智能问诊 - 移动端 App

基于 **uni-app** 跨端编译的 Android App,复用现有 FastAPI 后端(端口 8000)。

## 视觉风格

Apple Health 灵感:
- 浅灰背景 `#F2F2F7`
- 白色卡片 + 极浅分割线
- 主交互色克制(深灰 `#1C1C1E`,主操作不上重彩)
- 紧急/警示用 `#FF3B30`、成功用 `#34C759`、警示用 `#FF9500`

## 页面结构

底部 4 个 tab:
- **首页**(品牌入口 + 4 个能力入口 + 症状胶囊)
- **问诊**(完整对话 + 紧急度自动识别)
- **发现**(知识库 / 名医录 / 胸片分析 / 报告识别 4 个子页)
- **我的**(用户信息 + 问诊记录 + 设置)

## 开发环境

### 方案 A:HBuilderX(官方 IDE,Windows/Mac)
1. 下载 [HBuilderX](https://www.dcloud.io/hbuilderx.html)(免费)
2. 文件 → 打开目录 → 选择 `mobile/`
3. 运行 → 运行到手机或模拟器 → Android App-基座

### 方案 B:Docker 离线打包(Linux 推荐,无需 GUI)
一行命令本地出 APK,首次约 10-15 分钟,后续增量 1-2 分钟:
```bash
cd mobile
./scripts/build-apk.sh
# 产物:mobile/output/ai-doctor.apk
```

需要本机装 Docker,详细见 `BUILD.md` 第二节。

### 方案 C:CLI(命令行,适合自动化)
```bash
cd mobile
npm install
npm run build:app-android  # 编译 Android 工程
# 产物:unpackage/dist/build/app-android/
# 然后用 Gradle 编译 APK
```

## 打包 Android

```bash
# 发行 → 原生 APP-云打包,选 Android,生成 .apk
# 或者本地打包:
npm run build:app-android
```

打包前在 `manifest.json` 填 `appid`(DCloud 分配)。

## 后端地址配置

`src/api/index.js` 顶部:
```js
const BASE_URL = 'http://10.0.2.2:8000/api/v1'  // 模拟器
// 局域网真机:改成 http://192.168.x.x:8000/api/v1
// 生产:改成 https://api.your-domain.com/api/v1
```

- `10.0.2.2` 是 Android 模拟器访问宿主机的特殊 IP
- 真机调试需要电脑和手机在同一 WiFi,用电脑局域网 IP
- 后端 CORS 已放开,无需额外配置

## 目录结构

```
mobile/
├── src/
│   ├── pages/          # 所有页面(uni-app 文件路由)
│   │   ├── home/       # 首页
│   │   ├── chat/       # 问诊
│   │   ├── discover/   # 发现 + 4 个子页(knowledge/doctors/xray/ocr)
│   │   ├── me/         # 我的 + history
│   │   └── login/      # 登录
│   ├── api/            # 接口封装
│   ├── styles/         # 设计 token
│   ├── static/         # 静态资源(tabbar 图标等)
│   ├── App.vue         # 应用入口
│   ├── main.js
│   ├── pages.json      # 路由 + tabBar 配置
│   └── manifest.json   # App 配置
└── README.md
```

## 已实现 vs 待补全

✅ 已实现(全功能 7 页):
- 登录 / 注册入口
- 首页 + 4 个能力入口
- 智能问诊(完整对话 + 紧急度)
- 知识库(分类 + 搜索 + 详情)
- 名医录
- 胸片分析(上传 + 11 维结果展示)
- 报告识别(上传 + 简单结构化展示)
- 我的 + 问诊记录
- 4 tab 底部导航
- Token 管理 + 401 自动跳登录

⚠️ 占位/待补:
- tabBar 图标(已生成 1x1 占位 PNG,需替换为真实 81x81 黑白图标)
- App icon / 启动图(打包时配置)
- 推送通知(可选)
- 离线缓存(可选)

## 调试

- 模拟器:`http://10.0.2.2:8000` 访问后端
- 真机:用 `adb reverse tcp:8000 tcp:8000` 把后端端口反向映射到手机
- HBuilderX 控制台日志会显示请求/响应
