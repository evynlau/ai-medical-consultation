# 主题 / 调性

- **品牌定位**:**温煦的 C 端医疗 AI 助手**(类似「丁香医生」+「你的家庭医生」)
- **调性关键词**:柔和、有温度、克制的医疗青绿、专业可信、像朋友而非冷冰冰的 AI
- **目标用户**:对医疗有焦虑感的 C 端患者(尤其中老年)——「安心感」比「科技感」重要

---

# 全局设计 Token

> 新建 `frontend/src/styles/tokens.scss`,所有页面用 `@use` 引用,**统一替换现有 5 处 `#409EFF` 等临时色**。

## 1. 色彩(CSS 变量形式,SCSS 与 CSS 都可用)

```scss
:root {
  /* === 主色:薄雾青(青绿 = 医学+自然) === */
  --c-primary-50:  #E6F4F2;  /* 浅背景 */
  --c-primary-100: #C2E5E0;
  --c-primary-300: #7BC8BF;
  --c-primary-500: #4FB3A9;  /* 主色 */
  --c-primary-600: #3A8C84;  /* hover */
  --c-primary-700: #2A6862;  /* active */
  --c-primary-900: #163B37;  /* 文字 */

  /* === 辅色:暖白 / 暖灰(纸张感) === */
  --c-bg-soft:    #FAF7F2;  /* 暖白底 */
  --c-bg:         #F5F2EC;  /* 二级底 */
  --c-surface:    #FFFFFF;  /* 卡片 */
  --c-text-1:     #2A2926;  /* 主文字 */
  --c-text-2:     #5C5A56;  /* 次文字 */
  --c-text-3:     #8A8884;  /* 弱文字 */
  --c-border:     #ECE7DE;  /* 浅边框 */

  /* === 强调色:暖橙(温和警示) === */
  --c-warn-50:  #FCF1E8;
  --c-warn-500: #E89B6C;   /* 主警示 */
  --c-warn-700: #B26A3D;   /* 紧急强调 */

  /* === 状态色 === */
  --c-success: #5BA882;    /* 比 Element 绿柔和 */
  --c-danger:  #D8746A;    /* 暖红 */
  --c-info:    #6E8AB0;    /* 冷蓝灰 */
}
```

## 2. 字体

```scss
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, "PingFang SC",
               "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif;
  --font-serif: "Noto Serif SC", "Source Han Serif SC", "Songti SC", serif;
  --font-mono: "JetBrains Mono", "Fira Code", Consolas, monospace;

  /* 字号阶 */
  --fs-12: 12px;  --fs-14: 14px;  --fs-16: 16px;  --fs-18: 18px;
  --fs-20: 20px;  --fs-24: 24px;  --fs-32: 32px;  --fs-40: 40px;
  --fs-48: 48px;

  /* 字重 */
  --fw-regular: 400;  --fw-medium: 500;
  --fw-semibold: 600;  --fw-bold: 700;
}
```

**字体策略**:
- 正文:思源黑体 / 系统字(`--font-sans`)
- 大标题:**思源宋体**(`--font-serif`)—— 衬线带来「书籍感」,呼应医学权威
- 代码:等宽

## 3. 间距(4px 基线)

```scss
:root {
  --sp-1: 4px;   --sp-2: 8px;   --sp-3: 12px;  --sp-4: 16px;
  --sp-5: 20px;  --sp-6: 24px;  --sp-8: 32px;  --sp-10: 40px;
  --sp-12: 48px; --sp-16: 64px; --sp-20: 80px; --sp-24: 96px;
}
```

## 4. 圆角

```scss
:root {
  --r-sm: 6px;     /* 标签、小按钮 */
  --r-md: 12px;    /* 输入框、小卡 */
  --r-lg: 16px;    /* 卡片 */
  --r-xl: 24px;    /* 大卡、主容器 */
  --r-2xl: 32px;   /* 巨型容器 */
  --r-full: 9999px;/* 胶囊 */
}
```

## 5. 阴影(多层柔和,无生硬深色)

```scss
:root {
  --shadow-xs: 0 1px 2px rgba(42, 41, 38, 0.04);
  --shadow-sm: 0 2px 8px rgba(42, 41, 38, 0.06),
               0 1px 2px rgba(42, 41, 38, 0.04);
  --shadow-md: 0 8px 24px rgba(42, 41, 38, 0.08),
               0 2px 6px rgba(42, 41, 38, 0.04);
  --shadow-lg: 0 16px 40px rgba(42, 41, 38, 0.10),
               0 4px 12px rgba(42, 41, 38, 0.06);
  --shadow-glow: 0 0 40px rgba(79, 179, 169, 0.25);  /* 青绿辉光 */
}
```

## 6. 动效(微动 + 缓动,避免晃动)

```scss
:root {
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-fast: 150ms;
  --dur-base: 240ms;
  --dur-slow: 400ms;
}
```

---

# 改版前后对照

## Home.vue 改版前后

### ❌ 改版前
- Hero 区 1 个默认图标(160px 的 FirstAidKit 显得呆板)
- 8 个能力卡(8 个渐变圆,信息密度低,**两个图标重复 `Files`**)
- 12 个 Tag 凑成的快速症状(无设计感)
- 1 个 alert 免责声明(条文字)
- **没有任何品牌识别 / 信任元素 / 视觉记忆点**

### ✅ 改版后(见 `_design_samples/Home.design.html`)

**结构(从上到下)**:
1. **顶部导航**(全宽,常驻,品牌 logo + 路由 + 用户菜单)
2. **Hero 区**(分两列):
   - 左:**情感化大标题**「你的 AI 家庭医生,7×24 在线」+ 副文案 + 主按钮(薄雾青)+ 次按钮(描边)+ 数据条
   - 右:**插画/装饰**(抽象 SVG 装饰元素——光晕、几何医疗元素、抽象波纹)
3. **信任数据条**:**三栏**「已咨询 10,000+ · 知识库 600+ 篇 · 服务覆盖 35+ 科室」(数字 + 标签 + 简短说明)
4. **4 大能力卡片**(不是 8 个):每张卡片**上半部分是渐变插画区,下半部分是文字**,hover 抬升
5. **快速症状**:**胶囊按钮组**,hover 涟漪
6. **底部 CTA**:**更大的主按钮** + 免责声明

---

## Login.vue 改版前后

### ❌ 改版前
- 居中单卡片,简单 Tab + 表单
- **安全感不足**(医疗 app 登录需要信任感)

### ✅ 改版后
- **分屏布局**:
  - 左 50%:**品牌插画区**(渐变背景 + 抽象装饰 + 「你的健康,我们守护」+ 3 个 feature 标签)
  - 右 50%:**白底表单**(宽松排版 + 大输入框)
- 底部:微信/Apple ID 第三方登录占位(可点可不接)
- 右上:夜间模式 toggle

---

## Chat.vue 改版前后

### ❌ 改版前
- 顶部信息条 + 消息列表 + 输入框,单列布局
- AI 气泡单调,**紧急提示靠 alert 强行打断**
- 知识来源是普通 div,**没下划线/视觉提示**
- 无打字机效果

### ✅ 改版后
- **三栏式布局**:
  - 左 240px:**历史会话侧边栏**(可折叠)
  - 中 70%:聊天主区
  - 右 280px(可关闭):**知识来源 + 结构化分析面板**
- **AI 消息**:圆角 16px + 左侧主色细边 + 内部 markdown 渲染
- **紧急提示**:消息顶部淡红底色「紧急」徽章(自然融入,**不强行打断**)
- **打字机动画**:`<TypeWriter>` 组件,逐字渐显
- **快捷 chips**:空状态显示 4-6 个常见问题,点击直接发送
- 知识来源:**悬浮卡片**带图标(📚 书本)+ 类别色 + 相关度条

---

## Imaging/Analysis.vue 改版前后

### ❌ 改版前
- 警告 alert + el-upload 默认 + 表单 + 提交
- **无引导感,无进度可视化**

### ✅ 改版后
- **上传区**:自定义圆形拖拽区 + 渐变描边 + 胸片示例缩略图
- **AI 分析中**:**三段式进度可视化**(图像预处理 / 模型推理 / 结果生成)+ 心电图般进度条
- **结果区**:**左右分栏**:
  - 左 60%:原图 + Grad-CAM 叠加(透明度滑块)
  - 右 40%:18 维病理概率条形图(阳性的红高亮)
- **主诊断卡片**:顶置 + 醒目 + 双色(主诊断 / 建议)

---

# 实施计划(3 轮)

| 轮次 | 内容 | 交付物 |
|---|---|---|
| **Round 1**(本轮) | 设计稿 + `tokens.scss` + Home.vue 改版 | 你看到新 Home + 全局 Token |
| **Round 2** | Login.vue + Chat.vue | 分屏登录 + 三栏聊天 |
| **Round 3** | Imaging/Analysis.vue + OCR.vue | 进度可视化 + 双栏 OCR |

每轮**给你看实际效果** → 你的反馈 → 进入下一轮。

---

# 兼容性策略

**保留** Element Plus 组件库,但通过 CSS 变量**覆盖默认色**:
```scss
:root {
  --el-color-primary: var(--c-primary-500);
  --el-color-primary-light-3: var(--c-primary-300);
  --el-color-primary-light-7: var(--c-primary-100);
  --el-color-primary-light-9: var(--c-primary-50);
  --el-color-primary-dark-2: var(--c-primary-700);
  --el-border-radius-base: var(--r-md);
}
```
这样**所有 el-button / el-card / el-input 自动跟随新色**,无需逐个组件重写。

---

# 不做的事(显式排除)

- ❌ 不重写业务逻辑(script 部分)
- ❌ 不重写后端 API
- ❌ 不改 router 路由结构
- ❌ 不引入新 UI 库(继续用 Element Plus)
- ❌ 不做复杂动画库依赖(纯 CSS + Vue 过渡)
