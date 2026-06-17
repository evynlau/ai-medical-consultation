# AI 智能问诊系统 — 移动端 APP 设计开发规划

> 版本:v0.1 · 起草 2026-06-17
>
> **配套文档**:`mobile/BUILD.md`(打包步骤)/ `docs/DESIGN_PROPOSAL.md`(PC 端调性) / `mobile/README.md`(项目结构)
>
> **本规划遵循**:
> 1. **C 端优先**:把 PC Web 端的 6 大能力压缩进手机端,优先服务患者自助问诊;医生端继续用 Web 后台(数据量大、需要看全平台)
> 2. **页面骨架已就位**(`mobile/src/pages/` 共 14 个页面 / 4 tab / API 封装 / tokens.scss),**不新增页面,只做功能完整化 + UX 打磨**
> 3. **沿用 PC 端调性**:`docs/DESIGN_PROPOSAL.md` 已定青绿 + 暖白;本规划只补移动端特有规范(触控区/安全间距/系统字体)

---

## 一、定位与目标

**一句话定位**:把 PC Web 端的 **对话问诊 / 知识库 / OCR / 问诊历史 / 个人中心** 五个高频能力压缩进手机端,主打「晚上不舒服时,3 次点击见到 AI 医生」。

**MVP(V0)范围**:对话问诊(文字)+ 知识库浏览 + 历史记录 + 我的(资料/设置)
**V1.1 增量**:OCR 拍照识处方/报告 + 语音输入 + 紧急场景强提示
**V1.2 增量**:胸片分析(医生角色专属)+ 离线缓存 + 推送

**为什么这样切**:
- 患者端是**高频低门槛场景**(晚上不舒服要查),适合做 APP
- 医生端的影像/标注/管理后台在 Web 端更高效,**不重复造轮子**
- 增量按「对患者价值 × 实现成本」排:V0 必做;V1.1 是差异点;V1.2 锦上添花

---

## 二、技术选型

### 2.1 方案对比

| 方案 | 优势 | 劣势 | 推荐度 |
|---|---|---|---|
| **uni-app(已采用)** | 一次代码可产 H5 + 小程序 + APP,语法接近 Vue,生态全 | CLI **不产原生 Android 工程**,必须 HBuilderX GUI 云打包 | ⭐⭐⭐ 继续走 |
| **Capacitor** | `npx cap add android` 直接产 Android Studio 工程,Linux CLI 全跑通 | 要重写所有 `<view>` `<text>` 为标准 HTML,工作量等同重写(5-7 天) | ⭐⭐ 备选 |
| Flutter | 性能最好,UI 一致性最高 | 重学 Dart,Vue 代码全废,后端联调也得改 | ⭐ 否决 |
| React Native | JS 生态熟 | 性能不如 Flutter,Web 端代码无法复用 | ⭐ 否决 |

### 2.2 决策

**继续走 uni-app**。前置条件:解决 HBuilderX 云打包(走 DCloud 商业版云端,免费可用,有 5-10 分钟排队);若未来必须 Linux CLI 出包,再切 Capacitor 重写。**关键经验已记入 `app-packaging-uniapp` 记忆**。

---

## 三、信息架构与页面规划

### 3.1 底部 Tab(4 个,C 端患者视角)

```
┌──────────┬──────────┬──────────┬──────────┐
│  🏠 首页 │  💬 问诊 │  📚 发现 │  👤 我的 │
└──────────┴──────────┴──────────┴──────────┘
```

| Tab | 页面 | 核心功能 | 对应后端 API |
|---|---|---|---|
| **首页** | `pages/home/home` | 4 张功能入口卡(在线问诊/拍照识方/胸片自测/急救热线)+ 紧急提醒横幅 + 快捷症状 | `GET /admin/stats`(脱敏) |
| **问诊** | `pages/chat/chat` | 多轮对话(文字)+ 结构化分析弹窗 + 紧急识别 | `POST /consult`、`/messages`、`/agent/analyze` |
| **发现** | `pages/discover/discover` | 子 Tab 切换:知识库 / 名医录 / OCR / 胸片(医生角色) | `GET /knowledge`、`/doctors/search` |
| **我的** | `pages/me/me` | 资料 / 问诊历史 / OCR 记录 / 设置 / 退出 | `GET /user/me`、`GET /consult` |

### 3.2 页面清单(14 个,全部已存在,零新增)

```
mobile/src/pages/
├── home/home.vue               ✅
├── chat/chat.vue               ✅
├── me/
│   ├── me.vue                  ✅
│   └── history.vue             ✅
├── login/login.vue             ✅
└── discover/
    ├── discover.vue            ✅  (Tab 容器)
    ├── knowledge.vue           ✅
    ├── knowledge-detail.vue    ✅
    ├── doctors.vue             ✅
    ├── ocr.vue                 ✅
    └── xray.vue                ✅
```

**结论**:**不新增页面**;V0 工作重心在"已有页面的功能完整化 + UX 打磨 + 工程化补全"。

---

## 四、核心模块功能详设

### 4.1 💬 对话问诊(核心,80% 用户时长)

**4.1.1 多轮对话**
- 复用 `src/api/index.js` 的 `chat` 模块(`POST /consult/{id}/messages`)
- 消息气泡:用户右对齐主色底,AI 左对齐白底
- **连续追问引导**:AI 答复后,自动追加「是否还有:伴随症状 / 持续时间 / 既往史 / 用药情况?」快捷追问按钮(点击即发)
- **空状态**:首次进入显示 6 张快捷症状卡(头痛/发热/咳嗽/腹痛/失眠/皮肤),点击即发问

**4.1.2 语音输入(V1.1 增量,关键差异点)**
- 集成 `uni.getRecorderManager`(uni-app 跨端录音 API,无需原生插件)
- 录音 60 秒上限,自动转文字
- 波形可视化:用 `setInterval` + 随机柱状图(降级方案)

**4.1.3 结构化分析(报告卡)**
- 聊满 3 轮后,顶部显示「📋 生成分析报告」按钮
- 调 `POST /agent/analyze` 拿 JSON,渲染为报告卡(紧急度色条 / 可能病因列表 / 推荐科室 / 护理建议)
- **紧急度≥4 时强制弹窗**:大红色横幅 + 「立即拨打 120」按钮

**4.1.4 紧急识别**
- 后端已有 `urgency_detection` 逻辑,前端只负责渲染
- 触发关键词:胸痛/呼吸困难/剧烈头痛/大出血 → `urgency ≥ 4`
- UI:全屏红色遮罩 + 紧急电话 120 一键拨打(`uni.makePhoneCall`)

### 4.2 🏠 首页

**4.2.1 顶部 Banner**
- 问候语 + 当前时间(早晚不同文案)+ 未读问诊小红点
- 紧急提醒(若有 `urgency≥4` 未关闭问诊,大红色滚动条)

**4.2.2 4 张功能入口卡(2x2 宫格)**
```
┌──────────┬──────────┐
│ 💬 问诊  │ 📷 识方  │
│ 在线 AI  │ 拍照 OCR │
├──────────┼──────────┤
│ 🩻 胸片  │ 📚 知识库│
│ 上传分析 │ 健康科普 │
└──────────┴──────────┘
```
- 胸片入口:仅医生角色可见(从 `store.user.is_doctor || is_admin` 判定)
- 全部用 `navigateTo` 跳转,无权限直接 toast 提示登录

**4.2.3 快捷症状(展开式)**
- 折叠 8 个常见症状标签,点开直接进入 chat 并自动发送首条消息
- 标签数据硬编码在 `static/symptoms.json`

### 4.3 📚 发现(Tab 容器)

- 子 Tab 切换:`知识库` / `名医录`
- **知识库**:
  - 顶部搜索框(调 `/knowledge/search/query?q=`)
  - 分类 chips(疾病/药品/检查/指南)+ 列表
  - 详情页 `knowledge-detail.vue`:标题 + 正文(Markdown 渲染)+ 标签 + 来源
- **名医录**:
  - 医生卡片:头像 + 姓名 + 科室 + 简介
  - 详情(暂用弹窗,不做独立页)
- **OCR**:`discover/ocr.vue`,从相册/相机选图 → 上传 → 展示结构化结果
- **胸片**:`discover/xray.vue`,仅医生角色,调 `/imaging/pneumonia/analyze`,展示 18 维概率 + Grad-CAM 图

### 4.4 👤 我的

- 头像 + 昵称 + 角色徽章(医生/患者)
- 列表项:
  - 问诊历史(跳 `me/history.vue`)
  - OCR 记录(V1.1 新增入口,接 `/ocr/records`)
  - 设置(清理缓存/语言切换/关于)
  - 退出登录

---

## 五、UI 设计规范(对齐 PC 端 + 移动端适配)

### 5.1 调性

**沿用 `docs/DESIGN_PROPOSAL.md` 的青绿 + 暖白**;本节只补移动端特有规范。

### 5.2 主题色板(`mobile/src/styles/tokens.scss` 补全)

```scss
// 主色:沿用 PC 端青绿
$color-primary-500: #4FB3A9;
$color-primary-600: #3A8C84;
$color-primary-50:  #E6F4F2;

// 语义色
$color-success: #10B981;
$color-warning: #F59E0B;
$color-danger:  #EF4444;  // 紧急专用,避免误用

// 文字 / 背景
$color-text-1:  #2A2926;
$color-text-2:  #6B7280;
$color-bg:      #FAF7F2;  // 暖白底(对齐 PC)
$color-card:    #FFFFFF;

// 圆角 / 阴影
$radius-md: 12px;
$radius-lg: 16px;
$shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
```

### 5.3 移动端规范

- **触控区**:所有按钮 ≥ 44x44pt(iOS HIG 标准)
- **字号**:正文 15px,标题 17px,辅助文字 13px(老年用户友好)
- **间距**:4 / 8 / 12 / 16 / 20 / 24(4px 网格)
- **字体**:系统字体优先(`-apple-system` / `Roboto`),不引入 webfont(影响首屏)
- **安全区**:`padding-bottom: env(safe-area-inset-bottom)` 处理 iPhone 底部横条

---

## 六、技术实现要点

### 6.1 已有基础设施(复用)

- `src/api/index.js` — 后端 API 封装(已有)
- `src/styles/tokens.scss` — 设计变量(待补全)
- `pages.json` — 路由 + tabBar 配置(已有)
- `manifest.json` — AppID / 启动图 / 权限(已有)

### 6.2 待补的工程化(V0 必做)

- **HTTP 拦截器**:`uni.request` 拦截 401 → 清 token + 跳登录
- **Loading 规范**:`uni.showLoading` 全局封装,Promise 风格
- **错误兜底**:网络错误/超时统一 toast + 重试按钮
- **本地缓存**:token 用 `uni.setStorageSync`,问诊历史分页用 `uni.setStorage`(避免重复拉)
- **图片懒加载**:`<image lazy-load>` 已支持

### 6.3 角色权限

- `store.user.is_doctor || is_admin` 控制胸片入口显隐
- 路由守卫:`pages.json` 不支持,改在 `App.vue` 的 `onShow` 判定

### 6.4 跨端兼容点

- **语音**:H5 用 `MediaRecorder`,APP 用 `uni.getRecorderManager`
- **相机**:H5 用 `<input type=file capture>`,APP 用 `uni.chooseImage`(`sourceType: ['camera']`)
- **WebSocket**:统一用 `uni.connectSocket`,后端 `/api/ws/chat` 已通
- **后端地址**:`api/index.js` 顶部 `BASE_URL` 区分:

  | 场景 | URL |
  |---|---|
  | H5 dev | `http://localhost:8000/api/v1` |
  | APP 模拟器 | `http://10.0.2.2:8000/api/v1` |
  | APP 真机 | 电脑局域网 IP |
  | 生产 | 域名 + HTTPS |

---

## 七、打包与发布

### 7.1 打包路径选择(关键)

**当前实测状态**(详见 `mobile/BUILD.md` 和 `app-packaging-uniapp` 记忆):

- ❌ Linux CLI + Docker:uni-app CLI 不产原生工程,卡住
- ❌ Linux CLI + Java 17 + Android SDK:同上
- ✅ **Windows/Mac + HBuilderX 云打包**:走通,免费,5-10 分钟

**推荐方案**:
1. **首选**:Mac/Windows 装 HBuilderX → 菜单 → 发行 → 原生 APP-云打包
2. **备选**:云打包排队多时,切 Capacitor 重写(5-7 天工作量)
3. **轻量备选**:只发 H5,引导用户加桌面图标(PWA 风格,免审核)

### 7.2 上架前必做

- 隐私政策 + 用户协议 HTML 页(医疗类必需)
- AppIcon 多分辨率(`static/icons/app.png` 已有 200x200)
- 启动图(`static/logo.png` 已有 1024x1024)
- 备案:医疗类需 ICP + 互联网医疗信息服务前置审批(国内上架)

### 7.3 内部测试

- 蒲公英 / fir.im 上传 APK,生成下载链接
- 至少 5-10 个真机测试(iOS 1 + Android 主流 4-5)

---

## 八、开发排期(5 周 MVP)

| 周次 | 任务 | 交付物 | 验收标准 |
|---|---|---|---|
| **W1** | 基础架构补全:HTTP 拦截器 / Loading / 错误兜底 / token 持久化 / tokens.scss 补全 | 通用层代码 | 401 自动跳登录;网络错有提示;tokens 全部 token 化 |
| **W2** | chat 完整化:多轮 + 结构化分析 + 紧急识别 + 报告卡渲染 | chat.vue 优化 | 聊 3 轮可生成报告;紧急症状触发红弹窗 |
| **W3** | home + me:4 张入口卡 + 快捷症状 + 个人资料 | home/me 重写 | 4 个入口可达对应模块;资料可编辑 |
| **W4** | discover:知识库搜索/分类/详情 + 名医录 + OCR 拍照 | discover 套件 | 知识库语义搜索可用;OCR 拍照可上传 |
| **W5** | 打包发布:BUG 修复 + HBuilderX 云打包 + 蒲公英测试 | APK 链接 | 5 台真机跑通主流程 |

**V1.1 增量(再加 2 周)**:语音输入 + OCR 记录入口 + 推送
**V1.2 增量(再加 1 周)**:胸片分析(医生角色)+ 离线缓存 + 暗色模式

---

## 九、风险与决策点

| 风险 | 影响 | 应对 |
|---|---|---|
| **HBuilderX 必须 GUI 打包** | 阻塞上线 | 准备一台 Mac mini 或 Windows 机器专门打包;或备选 Capacitor 重写 |
| **医疗类审核严** | 上架被拒 | 提前做 ICP + 互联网医疗信息服务备案;接 DCloud 商务对接 |
| **uni-app 性能瓶颈**(长 chat 流) | 用户体验 | 用 `recycle-view` 虚拟列表;WebSocket 分帧渲染 |
| **大模型响应慢** | 体验差 | 前端加骨架屏 + 打字机效果;后端流式(已有 WS) |
| **隐私合规**(医疗数据) | 法律风险 | 端到端加密 + 匿名化 + 用户协议明示 |

---

## 十、待用户决策的 3 件事

1. **C 端 vs B 端优先**:APP 主打患者自助问诊(C 端),还是医生查房工具(B 端)?现状骨架是 C 端,但 `mobile/README.md` 写了"AI 家庭医生"。
2. **是否要胸片分析在 APP 上**:医生工作量大都在 Web 端,APP 上做胸片是锦上添花还是核心需求?
3. **打包方案**:
   - (a) 找一台 Mac/Windows 装 HBuilderX 云打包(1 小时搞定) ⭐ 推荐
   - (b) 等 HBuilderX Linux 版(不确定有没有)
   - (c) 切 Capacitor 重写(5-7 天工作量)

---

## 附录 A:相关文件位置

| 文件 | 作用 |
|---|---|
| `mobile/src/pages/` | 14 个页面(全部已存在) |
| `mobile/src/api/index.js` | 后端 API 封装 |
| `mobile/src/styles/tokens.scss` | 设计变量(待补全) |
| `mobile/src/pages.json` | 路由 + tabBar |
| `mobile/src/manifest.json` | AppID / 启动图 / 权限 |
| `mobile/BUILD.md` | 打包步骤详解 |
| `docs/DESIGN_PROPOSAL.md` | PC 端调性(沿用) |
| `docs/APP_PLAN.md` | 本文档 |

## 附录 B:关键记忆索引

- `app-packaging-uniapp` — uni-app CLI 不能产 Android,Docker 链路实测可行但卡在最后一步
- `ai-doctor-rag-system` — 后端 RAG 关键决策
- `project-overview` — 仓库结构 / 启动命令 / 端口 / 测试账号
