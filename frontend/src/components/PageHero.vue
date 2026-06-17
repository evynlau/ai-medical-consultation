<!--
  PageHero - 轻量页头 Hero
  与 Home.vue 的 Hero 视觉同源,但压缩到 ~200px:
  - 左侧:小徽章 + 大标题 + 副标题
  - 右侧:渐变圆形装饰 + 中心图标
  - 整体跟着 .page-container 走,内部用同款 tokens
-->
<template>
  <section class="page-hero" :class="`v${variant}`">
    <div class="page-hero-deco page-hero-deco-1" />
    <div class="page-hero-deco page-hero-deco-2" />

    <div class="page-hero-inner">
      <div class="page-hero-text">
        <div v-if="badge" class="page-hero-eyebrow">
          <span class="pulse" />
          <span>{{ badge }}</span>
        </div>
        <h1 class="page-hero-title">
          <span class="accent">{{ title }}</span>
        </h1>
        <p v-if="subtitle" class="page-hero-subtitle">{{ subtitle }}</p>
      </div>

      <div class="page-hero-visual">
        <div class="ring ring-1" />
        <div class="ring ring-2" />
        <div class="center-icon">
          <el-icon :size="44" color="#fff">
            <component :is="icon" />
          </el-icon>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  /** 顶部小徽章文案(可省略) */
  badge: { type: String, default: '' },
  /** 主标题(高亮用 .accent 着色) */
  title: { type: String, required: true },
  /** 副标题(可省略) */
  subtitle: { type: String, default: '' },
  /** 右侧图标(传 Element Plus 图标组件名) */
  icon: { type: [String, Object, Function], required: true },
  /** 配色变体: 1=青绿(默认) 2=冷蓝 3=暖橙 4=森林 5=玫瑰金 */
  variant: { type: Number, default: 1 },
})
</script>

<style lang="scss" scoped>
@use '@/styles/tokens.scss' as t;

.page-hero {
  position: relative;
  overflow: hidden;
  padding: t.sp(10) 0 t.sp(8);
  background: linear-gradient(160deg,
    t.c('bg-soft') 0%,
    t.c('primary-50') 60%,
    t.c('primary-100') 100%);
  border-radius: t.r('xl');
  margin-bottom: t.sp(6);
  box-shadow: t.shadow('sm');

  /* 不同 variant 走不同渐变(与 Home 五张能力卡呼应) */
  &.v1 { background: linear-gradient(160deg, t.c('bg-soft') 0%, t.c('primary-50') 60%, t.c('primary-100') 100%); }
  &.v2 { background: linear-gradient(160deg, t.c('bg-soft') 0%, #E8EFF7 60%, #D6E3F0 100%); }
  &.v3 { background: linear-gradient(160deg, t.c('bg-soft') 0%, #FCEEDF 60%, #F7DCC0 100%); }
  &.v4 { background: linear-gradient(160deg, t.c('bg-soft') 0%, #E4F1EA 60%, #C9E2D5 100%); }
  &.v5 { background: linear-gradient(160deg, t.c('bg-soft') 0%, #F4E0E4 60%, #E8C5CE 100%); }
}

.page-hero-deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}
.page-hero-deco-1 {
  top: -40%;
  right: -10%;
  width: 360px;
  height: 360px;
  background: radial-gradient(circle, rgba(79, 179, 169, 0.18) 0%, transparent 70%);
}
.page-hero-deco-2 {
  bottom: -60%;
  left: -10%;
  width: 280px;
  height: 280px;
  background: radial-gradient(circle, rgba(232, 155, 108, 0.10) 0%, transparent 70%);
}

.page-hero-inner {
  position: relative;
  z-index: 1;
  padding: 0 t.sp(8);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: t.sp(8);
}

.page-hero-text {
  flex: 1;
  min-width: 0;
}

.page-hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: t.sp(2);
  padding: 4px 12px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid t.c('primary-100');
  border-radius: t.r('full');
  font-size: 12px;
  color: t.c('primary-700');
  margin-bottom: t.sp(3);
  box-shadow: t.shadow('xs');

  .pulse {
    width: 7px;
    height: 7px;
    background: t.c('success');
    border-radius: 50%;
    animation: pulse 2s infinite;
  }
}

.page-hero-title {
  font-family: t.font("serif");
  font-size: clamp(24px, 3.2vw, 32px);
  font-weight: 700;
  line-height: 1.25;
  margin: 0 0 t.sp(2);
  letter-spacing: -0.01em;

  .accent {
    background: linear-gradient(135deg, t.c('primary-600'), t.c('primary-500'));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

/* variant 下的 accent 渐变要写在父级 .page-hero 上 */
.v1 .page-hero-title .accent { background: linear-gradient(135deg, t.c('primary-600'), t.c('primary-500')); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.v2 .page-hero-title .accent { background: linear-gradient(135deg, #4A6A95, #6E8AB0); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.v3 .page-hero-title .accent { background: linear-gradient(135deg, t.c('warn-700'), t.c('warn-500')); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.v4 .page-hero-title .accent { background: linear-gradient(135deg, #3E8762, #5BA882); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.v5 .page-hero-title .accent { background: linear-gradient(135deg, #A6566A, #C97B8A); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }

.page-hero-subtitle {
  font-size: 14px;
  line-height: 1.6;
  color: t.c('text-2');
  margin: 0;
  max-width: 560px;
}

/* 右侧装饰 */
.page-hero-visual {
  position: relative;
  flex-shrink: 0;
  width: 140px;
  height: 140px;
}

.ring {
  position: absolute;
  border-radius: 50%;
  animation: float 6s ease-in-out infinite;
}
.ring-1 {
  inset: 0;
  background: linear-gradient(135deg, rgba(79, 179, 169, 0.18), rgba(232, 155, 108, 0.10));
}
.ring-2 {
  inset: 18%;
  background: linear-gradient(135deg, t.c('primary-500'), t.c('primary-700'));
  box-shadow: t.shadow('glow');
  animation-delay: -2s;
}

.v2 .ring-1 { background: linear-gradient(135deg, rgba(110, 138, 176, 0.20), rgba(110, 138, 176, 0.10)); }
.v2 .ring-2 { background: linear-gradient(135deg, #6E8AB0, #4A6A95); }
.v3 .ring-1 { background: linear-gradient(135deg, rgba(232, 155, 108, 0.20), rgba(232, 155, 108, 0.10)); }
.v3 .ring-2 { background: linear-gradient(135deg, t.c('warn-500'), t.c('warn-700')); }
.v4 .ring-1 { background: linear-gradient(135deg, rgba(91, 168, 130, 0.20), rgba(91, 168, 130, 0.10)); }
.v4 .ring-2 { background: linear-gradient(135deg, #5BA882, #3E8762); }
.v5 .ring-1 { background: linear-gradient(135deg, rgba(201, 123, 138, 0.20), rgba(201, 123, 138, 0.10)); }
.v5 .ring-2 { background: linear-gradient(135deg, #C97B8A, #A6566A); }

.center-icon {
  position: absolute;
  inset: 18%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

/* 响应式:小屏隐藏右侧视觉 */
@media (max-width: 720px) {
  .page-hero-inner {
    flex-direction: column;
    align-items: flex-start;
    padding: 0 t.sp(5);
  }
  .page-hero-visual { display: none; }
  .page-hero { padding: t.sp(8) 0 t.sp(6); border-radius: t.r('lg'); }
}
</style>
