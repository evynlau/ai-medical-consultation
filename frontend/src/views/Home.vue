<template>
  <div class="home">
    <!-- 顶部导航由 App.vue 全局提供,此处不重复 -->

    <!-- Hero 区 -->
    <section class="hero">
      <div class="hero-deco hero-deco-1"></div>
      <div class="hero-deco hero-deco-2"></div>

      <div class="hero-inner">
        <div class="hero-text">
          <div class="hero-eyebrow">
            <span class="pulse"></span>
            <span>7×24 在线 · 600+ 篇医学知识库</span>
          </div>
          <h1 class="hero-title">
            你的 <span class="accent">AI 家庭医生</span><br>
            把安心,放进每一次对话
          </h1>
          <p class="hero-subtitle">
            基于大型语言模型、医学知识库与多模态影像分析,
            随时为您提供专业、可解释的健康咨询。
            胸痛、发热、慢病管理,我们都在。
          </p>
          <div class="hero-actions">
            <button class="btn btn-primary btn-xl" @click="quickStart">立即开始问诊 →</button>
            <button class="btn btn-outline btn-xl" @click="$router.push('/knowledge')">浏览知识库</button>
          </div>
          <div class="hero-trust">
            <div class="trust-item">
              <div class="trust-num">10,000+</div>
              <div class="trust-lbl">已服务用户</div>
            </div>
            <div class="trust-item">
              <div class="trust-num">98.6%</div>
              <div class="trust-lbl">满意度</div>
            </div>
            <div class="trust-item">
              <div class="trust-num">600+</div>
              <div class="trust-lbl">知识库条目</div>
            </div>
          </div>
        </div>

        <div class="hero-visual">
          <div class="ring ring-1"></div>
          <div class="ring ring-2"></div>
          <div class="ring ring-3"></div>
          <div class="pulse-dot dot-1"></div>
          <div class="pulse-dot dot-2"></div>
          <div class="center-icon">
            <el-icon :size="80" color="#fff"><FirstAidKit /></el-icon>
          </div>
          <svg class="svg-wave" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M50 200 L150 200 L170 180 L190 220 L210 160 L230 200 L350 200"
              stroke="rgba(255,255,255,0.40)" stroke-width="2" fill="none" />
          </svg>
        </div>
      </div>
    </section>

    <!-- 信任数据条 -->
    <div class="trust-strip">
      <div class="trust-cell">
        <div class="cell-num">35+</div>
        <div class="cell-lbl">覆盖临床科室</div>
      </div>
      <div class="trust-cell">
        <div class="cell-num">18 类</div>
        <div class="cell-lbl">胸片病理识别</div>
      </div>
      <div class="trust-cell">
        <div class="cell-num">7×24h</div>
        <div class="cell-lbl">全天候响应</div>
      </div>
      <div class="trust-cell">
        <div class="cell-num">三重校核</div>
        <div class="cell-lbl">知识库 + 专家 + 医生</div>
      </div>
    </div>

    <!-- 4 大能力卡片 -->
    <section class="features-section">
      <div class="section-eyebrow">
        <span class="pill">CORE CAPABILITIES</span>
      </div>
      <h2 class="section-title">五大核心能力,守护你的健康</h2>
      <p class="section-subtitle">从日常咨询到专科诊断,一站式的医疗 AI 助手</p>

      <div class="features-grid">
        <div
          v-for="f in features"
          :key="f.title"
          class="feature-card"
          :class="`v${f.variant}`"
          @click="$router.push(f.route)"
        >
          <div class="visual">
            <img :src="f.illustration" :alt="f.title" class="visual-img" />
          </div>
          <div class="body">
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
            <span class="tag">{{ f.tag }} →</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 快速症状 -->
    <section class="symptom-section">
      <div class="symptom-cloud">
        <div class="lbl">常见症状,快速咨询</div>
        <div class="tags">
          <span
            v-for="s in commonSymptoms"
            :key="s"
            class="symptom-pill"
            @click="quickAsk(s)"
          >
            {{ s }}
          </span>
        </div>
      </div>
    </section>

    <!-- 免责声明 -->
    <section class="cta-section">
      <div class="cta-disclaimer">
        <el-icon class="cta-icon" :size="20"><WarningFilled /></el-icon>
        <div>
          <strong>重要提醒</strong><br>
          本系统提供的所有健康建议仅供参考,不能替代专业医生的面诊和检查。
          如出现紧急情况(剧烈胸痛、呼吸困难、大出血、意识障碍等),
          请立即拨打 <strong>120</strong> 或前往最近的医院急诊。
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const chatStore = useChatStore()
const userStore = useUserStore()

const isLoggedIn = computed(() => !!userStore.token)

/**
 * 4 大核心能力(原 8 个压缩到 4 个,信息更聚焦)
 * variant 决定渐变色: v1=青绿 v2=冷蓝 v3=暖橙 v4=森林
 */
const features = [
  {
    title: '智能问诊',
    desc: '多轮对话收集症状，AI 给出可能病因与建议，陪你梳理每一次不适。',
    illustration: new URL('@/assets/illustrations/feature-1-consult.png', import.meta.url).href,
    variant: 1,
    tag: '开始咨询',
    route: '/chat',
  },
  {
    title: '胸片分析',
    desc: '18 维病理多分类，Grad-CAM 可视化，辅助医生阅片，定位更准。',
    illustration: new URL('@/assets/illustrations/feature-2-xray.png', import.meta.url).href,
    variant: 2,
    tag: '上传胸片',
    route: '/imaging',
  },
  {
    title: '报告识别',
    desc: '拍照即识别处方 / 检查报告，自动结构化为可机读 JSON，二次解读。',
    illustration: new URL('@/assets/illustrations/feature-3-ocr.png', import.meta.url).href,
    variant: 3,
    tag: '上传图片',
    route: '/ocr',
  },
  {
    title: '知识库',
    desc: '600+ 篇医学指南，基于公开权威（中华医学会 / ESC / NCCN），语义精准检索。',
    illustration: new URL('@/assets/illustrations/feature-4-kb.png', import.meta.url).href,
    variant: 4,
    tag: '浏览知识',
    route: '/knowledge',
  },
  {
    title: '名医录',
    desc: '按科室、医院、疾病、城市筛选名医，AI 智能问答直接帮你找到合适的医生。',
    illustration: new URL('@/assets/illustrations/feature-5-doctors.png', import.meta.url).href,
    variant: 5,
    tag: '查找名医',
    route: '/doctors',
  },
]

const commonSymptoms = [
  '头痛', '发热', '咳嗽', '腹痛', '腹泻', '胸痛',
  '心悸', '失眠', '过敏', '皮疹', '咽痛', '乏力',
]

const quickStart = () => {
  router.push('/chat')
}

const quickAsk = async (symptom) => {
  await chatStore.startConsultation(`最近${symptom},请帮我分析一下`)
  router.push('/chat')
}
</script>

<style lang="scss" scoped>
@use '@/styles/tokens.scss' as t;

.home {
  background: t.c('bg-soft');
  min-height: 100vh;
  padding-bottom: t.sp(16);
}

/* ============================================
   顶部导航
   ============================================ */
.top-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  height: 64px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid t.c('border');
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 t.sp(8);
}

.brand {
  display: flex;
  align-items: center;
  gap: t.sp(2);
  cursor: pointer;
}

.brand-icon {
  width: 36px;
  height: 36px;
  border-radius: t.r('md');
  background: linear-gradient(135deg, t.c('primary-500'), t.c('primary-700'));
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: 300;
  box-shadow: 0 4px 12px rgba(79, 179, 169, 0.30);
}

.brand-name {
  font-family: t.font("serif");
  font-size: 20px;
  font-weight: 700;
  color: t.c('primary-700');
  letter-spacing: 0.02em;
}

.nav-links {
  display: flex;
  gap: t.sp(2);

  a {
    padding: t.sp(2) t.sp(4);
    border-radius: t.r('md');
    font-size: 14px;
    color: t.c('text-2');
    cursor: pointer;
    transition: all t.dur("base") t.ease("out");

    &:hover {
      color: t.c('primary-600');
      background: t.c('primary-50');
    }
  }
}

.nav-actions {
  display: flex;
  gap: t.sp(2);
  align-items: center;
}

/* ============================================
   按钮(对齐设计稿 .btn)
   ============================================ */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: t.sp(2);
  padding: t.sp(3) t.sp(5);
  border-radius: t.r('md');
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all t.dur("base") t.ease("out");
  font-family: inherit;
  line-height: 1.2;
}
.btn-primary {
  background: t.c('primary-500');
  color: #fff;
  box-shadow: 0 4px 12px rgba(79, 179, 169, 0.30);
}
.btn-primary:hover {
  background: t.c('primary-600');
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(79, 179, 169, 0.40);
}
.btn-outline {
  background: transparent;
  color: t.c('primary-700');
  border-color: t.c('primary-300');
}
.btn-outline:hover {
  background: t.c('primary-50');
  color: t.c('primary-600');
  border-color: t.c('primary-500');
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(79, 179, 169, 0.18);
}
.btn-outline:active {
  transform: translateY(0);
  background: t.c('primary-100');
  box-shadow: none;
}
.btn-xl {
  padding: t.sp(5) t.sp(8);
  font-size: 18px;
  font-weight: 600;
}

/* ============================================
   Hero 区
   ============================================ */
.hero {
  position: relative;
  overflow: hidden;
  padding: t.sp(12) t.sp(8) t.sp(20);  /* 顶部留 48px,避免与 App 全局导航 60px 紧贴 */
  background: linear-gradient(160deg,
    t.c('bg-soft') 0%,
    t.c('primary-50') 60%,
    t.c('primary-100') 100%);
}

.hero-deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}

.hero-deco-1 {
  top: -20%;
  right: -10%;
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(79, 179, 169, 0.18) 0%, transparent 70%);
}

.hero-deco-2 {
  bottom: -30%;
  left: -10%;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(232, 155, 108, 0.10) 0%, transparent 70%);
}

.hero-inner {
  position: relative;
  z-index: 1;
  max-width: 1320px;
  margin: 0 auto;
  padding: 0 t.sp(6);
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr);
  gap: t.sp(12);
  align-items: center;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: t.sp(2);
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid t.c('primary-100');
  border-radius: t.r('full');
  font-size: 13px;
  color: t.c('primary-700');
  margin-bottom: t.sp(5);
  box-shadow: t.shadow('xs');

  .pulse {
    width: 8px;
    height: 8px;
    background: t.c('success');
    border-radius: 50%;
    animation: pulse 2s infinite;
  }
}

.hero-title {
  font-family: t.font("serif");
  font-size: 56px;
  font-weight: 700;
  line-height: 1.2;
  color: t.c('text-1');
  margin-bottom: t.sp(5);
  letter-spacing: -0.02em;

  .accent {
    background: linear-gradient(135deg, t.c('primary-600'), t.c('primary-500'));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.hero-subtitle {
  font-size: 18px;
  line-height: 1.7;
  color: t.c('text-2');
  margin-bottom: t.sp(8);
  max-width: 540px;
}

.hero-actions {
  display: flex;
  gap: t.sp(4);
  margin-bottom: t.sp(8);
  flex-wrap: wrap;
}

.hero-trust {
  display: flex;
  gap: t.sp(8);
  padding-top: t.sp(6);
  border-top: 1px solid t.c('primary-100');
  flex-wrap: wrap;
}

.trust-item {
  .trust-num {
    font-family: t.font("serif");
    font-size: clamp(24px, 2.4vw, 32px);
    font-weight: 700;
    color: t.c('primary-700');
    line-height: 1;
  }

  .trust-lbl {
    font-size: 13px;
    color: t.c('text-3');
    margin-top: t.sp(1);
  }
}

/* 右侧装饰区 */
.hero-visual {
  position: relative;
  aspect-ratio: 1 / 1;
  max-width: 480px;
  width: 100%;
  margin-left: auto;
}

.ring {
  position: absolute;
  border-radius: 50%;
  animation: float 6s ease-in-out infinite;
}

.ring-1 {
  inset: 0;
  background: linear-gradient(135deg, rgba(79, 179, 169, 0.12), rgba(232, 155, 108, 0.08));
}

.ring-2 {
  inset: 8%;
  background: linear-gradient(135deg, rgba(79, 179, 169, 0.20), rgba(122, 200, 191, 0.15));
  animation-delay: -2s;
}

.ring-3 {
  inset: 18%;
  background: linear-gradient(135deg, t.c('primary-500'), t.c('primary-700'));
  box-shadow: t.shadow('glow');
}

.pulse-dot {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.dot-1 {
  top: 25%;
  left: 30%;
  background: t.c('warn-500');
  animation: pulse-warn 2s infinite;
}

.dot-2 {
  top: 60%;
  right: 15%;
  background: t.c('primary-500');
  animation: pulse 2s infinite;
  animation-delay: -1s;
}

.center-icon {
  position: absolute;
  inset: 18%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.svg-wave {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

/* ============================================
   信任数据条
   ============================================ */
.trust-strip {
  max-width: 1320px;
  margin: -60px auto 0;
  padding: t.sp(6) t.sp(8);
  background: t.c('surface');
  border-radius: t.r('xl');
  box-shadow: t.shadow('md');
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: t.sp(4);
  position: relative;
  z-index: 2;
}

.trust-cell {
  text-align: center;
  padding: 0 t.sp(3);
  border-right: 1px solid t.c('border');

  &:last-child {
    border-right: none;
  }
}

.cell-num {
  font-family: t.font("serif");
  font-size: clamp(26px, 2.6vw, 36px);
  font-weight: 700;
  color: t.c('primary-600');
  line-height: 1;
}

.cell-lbl {
  font-size: 13px;
  color: t.c('text-2');
  margin-top: t.sp(2);
}

/* ============================================
   4 大能力卡片
   ============================================ */
.features-section {
  max-width: 1320px;
  margin: 0 auto;
  padding: t.sp(20) t.sp(6) t.sp(16);
}

.section-eyebrow {
  text-align: center;
  margin-bottom: t.sp(3);
}

.pill {
  display: inline-block;
  padding: 4px 14px;
  background: t.c('primary-50');
  color: t.c('primary-700');
  border-radius: t.r('full');
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.05em;
}

.section-title {
  text-align: center;
  font-family: t.font("serif");
  font-size: 36px;
  font-weight: 700;
  color: t.c('text-1');
  margin-bottom: t.sp(3);
}

.section-subtitle {
  text-align: center;
  font-size: 16px;
  color: t.c('text-2');
  margin-bottom: t.sp(12);
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: t.sp(5);
}

.feature-card {
  background: t.c('surface');
  border-radius: t.r('xl');
  overflow: hidden;
  box-shadow: t.shadow('sm');
  transition: all t.dur("base") t.ease("out");
  cursor: pointer;
  border: 1px solid t.c('border');
  display: flex;            /* 让 .body 内的 flex: 1 生效,把 tag 推到底 */
  flex-direction: column;

  &:hover {
    transform: translateY(-6px);
    box-shadow: t.shadow('lg');
    border-color: t.c('primary-100');
  }

  .visual {
    aspect-ratio: 4 / 3;
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    overflow: hidden;
    /* 渐变退到"色温"层,不再抢主体视觉 */
    background: linear-gradient(135deg, rgba(255,255,255,0.6), rgba(255,255,255,0.2));

    .visual-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      object-position: center;
      display: block;
      transition: transform t.dur("slow") t.ease("out");
    }
  }

  &:hover .visual-img {
    transform: scale(1.04);
  }

  /* 顶部色条:用 6px 高的色带呼应 v1-v5 主色,保留品牌识别但不再霸占整块 */
  &.v1 .visual { border-bottom: 6px solid #4FB3A9; }
  &.v2 .visual { border-bottom: 6px solid #6E8AB0; }
  &.v3 .visual { border-bottom: 6px solid #E89B6C; }
  &.v4 .visual { border-bottom: 6px solid #5BA882; }
  &.v5 .visual { border-bottom: 6px solid #C97B8A; }  /* 名医录:玫瑰金 */

  .body {
    padding: t.sp(6);
    /* 把 tag 推到底部,与同行卡片底部对齐 */
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  h3 {
    font-size: 20px;
    font-weight: 600;
    color: t.c('text-1');
    margin-bottom: t.sp(2);
  }

  p {
    font-size: 14px;
    color: t.c('text-2');
    line-height: 1.6;
    margin: 0;
    flex: 1;  /* 占满剩余空间,把 .tag 挤到底 */
  }

  .tag {
    display: inline-block;
    margin-top: t.sp(4);
    font-size: 12px;
    color: t.c('primary-600');
    font-weight: 500;
    transition: transform t.dur("base") t.ease("out");
  }

  &:hover .tag {
    transform: translateX(4px);
  }
}

/* ============================================
   快速症状胶囊
   ============================================ */
.symptom-section {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 t.sp(8);
}

.symptom-cloud {
  background: t.c('surface');
  border-radius: t.r('2xl');
  padding: t.sp(8);
  box-shadow: t.shadow('sm');
  border: 1px solid t.c('border');
}

.lbl {
  font-size: 13px;
  color: t.c('text-3');
  margin-bottom: t.sp(4);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: t.sp(3);
}

.symptom-pill {
  display: inline-flex;
  align-items: center;
  padding: 10px 18px;
  background: t.c('bg-soft');
  border: 1px solid t.c('border');
  border-radius: t.r('full');
  font-size: 14px;
  color: t.c('text-1');
  cursor: pointer;
  user-select: none;
  transition: all t.dur("base") t.ease("out");

  &:hover {
    background: t.c('primary-500');
    color: #fff;
    border-color: t.c('primary-500');
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(79, 179, 169, 0.30);
  }
}

/* ============================================
   免责声明
   ============================================ */
.cta-section {
  max-width: 1280px;
  margin: 0 auto;
  padding: t.sp(12) t.sp(8) 0;
}

.cta-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: t.sp(3);
  max-width: 720px;
  margin: 0 auto;
  padding: t.sp(4) t.sp(5);
  background: t.c('warn-50');
  border: 1px solid rgba(232, 155, 108, 0.20);
  border-radius: t.r('lg');
  text-align: left;
  font-size: 13px;
  color: t.c('text-2');
  line-height: 1.7;

  strong {
    color: t.c('warn-700');
  }
}

.cta-icon {
  color: t.c('warn-700');
  flex-shrink: 0;
  margin-top: 2px;
}

/* ============================================
   响应式
   ============================================ */
@media (max-width: 1280px) {
  // 5 列卡片减到 3 列(在 1024-1280 区间保持紧凑)
  .features-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  // 信任条改为 2 列
  .trust-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: t.sp(4);
  }
  .trust-cell:nth-child(2) { border-right: none; }
  .trust-cell:nth-child(1),
  .trust-cell:nth-child(2) {
    border-bottom: 1px solid t.c('border');
    padding-bottom: t.sp(4);
  }
  .trust-cell:nth-child(3) { border-bottom: 1px solid t.c('border'); padding-top: t.sp(4); }
  .hero { padding: t.sp(20) t.sp(6) t.sp(16); }
  .features-section { padding-top: t.sp(16); }
}

@media (max-width: 1024px) {
  // 中屏继续降到 2 列
  .features-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 960px) {
  // Hero 单列,视觉区隐藏(由数据条装饰)
  .hero-inner { grid-template-columns: 1fr; gap: t.sp(8); }
  .hero-visual { display: none; }
  .hero-actions { flex-direction: row; }
  .hero-trust { flex-wrap: wrap; gap: t.sp(6) t.sp(8); }
  .nav-links { display: none; }
  .top-nav { padding: 0 t.sp(4); }
}

@media (max-width: 640px) {
  // 4 列卡 → 1 列,信任条 → 1 列
  .features-grid { grid-template-columns: 1fr; }
  .trust-strip { grid-template-columns: 1fr; }
  .trust-cell {
    border-right: none !important;
    border-bottom: 1px solid t.c('border');
    padding: t.sp(4) 0;
  }
  .trust-cell:last-child { border-bottom: none; }
  .hero { padding: t.sp(12) t.sp(4) t.sp(10); }
  .hero-title { font-size: 32px; }
  .hero-actions { flex-direction: column; width: 100%; }
  .hero-actions > * { width: 100%; }
  .features-section { padding: t.sp(12) t.sp(4); }
  .symptom-section, .cta-section { padding-left: t.sp(4); padding-right: t.sp(4); }
  .symptom-cloud { padding: t.sp(5); }
  .trust-strip { margin-top: -30px; padding: t.sp(4); }
  .section-title { font-size: 24px; }
  .section-subtitle { font-size: 14px; }
  .nav-actions { gap: t.sp(1); }
}
</style>
