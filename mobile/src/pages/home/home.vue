<template>
  <view class="home-page">
    <!-- 顶部状态栏占位 -->
    <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />

    <!-- 顶部问候 -->
    <view class="greeting">
      <view class="hello">
        <view class="hello-title">你好{{ isLogin ? `,${user.nickname || user.username || '用户'}` : '' }}</view>
        <view class="hello-sub">AI 家庭医生 · 7×24 在线</view>
      </view>
      <view v-if="!isLogin" class="login-btn" @click="goLogin">登录</view>
    </view>

    <!-- 紧急提示卡(放最上,Apple Health 风格强引导) -->
    <view v-if="showEmergency" class="emergency-card">
      <view class="em-title">⚠ 紧急提醒</view>
      <view class="em-desc">
        本系统仅供参考,不能替代专业医生诊断。<br>
        出现剧烈胸痛、呼吸困难、意识障碍等请立即拨打 120。
      </view>
    </view>

    <!-- 主要行动:开始问诊 -->
    <view class="primary-cta" @click="goChat">
      <view class="cta-text">
        <view class="cta-title">描述症状 · 开始问诊</view>
        <view class="cta-sub">多轮对话 · 知识库参考</view>
      </view>
      <view class="cta-arrow">›</view>
    </view>

    <!-- 4 个能力入口(2x2 网格) -->
    <view class="grid">
      <view class="grid-item" @click="go('/pages/discover/xray')">
        <view class="grid-icon icon-1">🩻</view>
        <view class="grid-title">胸片分析</view>
        <view class="grid-desc">多分类识别</view>
      </view>
      <view class="grid-item" @click="go('/pages/discover/ocr')">
        <view class="grid-icon icon-2">📄</view>
        <view class="grid-title">报告识别</view>
        <view class="grid-desc">拍照即识别</view>
      </view>
      <view class="grid-item" @click="go('/pages/discover/knowledge')">
        <view class="grid-icon icon-3">📚</view>
        <view class="grid-title">知识库</view>
        <view class="grid-desc">医学指南</view>
      </view>
      <view class="grid-item" @click="go('/pages/discover/doctors')">
        <view class="grid-icon icon-4">👨‍⚕️</view>
        <view class="grid-title">名医录</view>
        <view class="grid-desc">按科室查找</view>
      </view>
    </view>

    <!-- 常见症状胶囊(Apple Health 风格横向滚动) -->
    <view class="symptoms">
      <view class="section-title">常见症状</view>
      <view class="pill-list">
        <view v-for="s in symptoms" :key="s" class="pill" @click="quickAsk(s)">{{ s }}</view>
      </view>
    </view>

    <!-- 底部 tabBar 占位(避免内容被遮挡) -->
    <view class="tabbar-placeholder" />
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getUser, getToken } from '@/api/index.js'

const statusBarHeight = ref(20)
try {
  // 读取系统状态栏高度(uni-app API)
  const sys = uni.getSystemInfoSync()
  statusBarHeight.value = sys.statusBarHeight || 20
} catch {}

const user = ref(getUser() || {})
const isLogin = computed(() => !!getToken())
const showEmergency = ref(true)

const symptoms = ['头痛', '发热', '咳嗽', '腹痛', '腹泻', '胸痛', '心悸', '失眠', '过敏', '皮疹', '咽痛', '乏力']

const go = (url) => {
  if (!isLogin.value && (url.includes('xray') || url.includes('ocr'))) {
    return uni.showToast({ title: '请先登录', icon: 'none' })
  }
  uni.navigateTo({ url })
}
const goChat = () => {
  if (!isLogin.value) return uni.navigateTo({ url: '/pages/login/login' })
  uni.switchTab({ url: '/pages/chat/chat' })
}
const goLogin = () => uni.navigateTo({ url: '/pages/login/login' })
const quickAsk = (s) => {
  if (!isLogin.value) return uni.navigateTo({ url: '/pages/login/login' })
  uni.setStorageSync('pending_complaint', `最近${s},请帮我分析一下`)
  uni.switchTab({ url: '/pages/chat/chat' })
}
</script>

<style lang="scss" scoped>
.home-page {
  min-height: 100vh;
  background: #F2F2F7;
  padding: 0 16px;
  box-sizing: border-box;
}

.greeting {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 0 20px;
  .hello-title {
    font-size: 28px;
    font-weight: 700;
    color: #1C1C1E;
    line-height: 1.2;
  }
  .hello-sub {
    margin-top: 4px;
    font-size: 13px;
    color: #8E8E93;
  }
}
.login-btn {
  padding: 6px 14px;
  background: #1C1C1E;
  color: #fff;
  border-radius: 14px;
  font-size: 14px;
}

.emergency-card {
  background: #FFE5E3;
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 16px;
  .em-title { font-size: 15px; font-weight: 600; color: #FF3B30; margin-bottom: 6px; }
  .em-desc { font-size: 13px; color: #3C3C43; line-height: 1.6; }
}

.primary-cta {
  display: flex;
  align-items: center;
  background: #1C1C1E;
  color: #fff;
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 16px;
  .cta-text { flex: 1; }
  .cta-title { font-size: 17px; font-weight: 600; }
  .cta-sub { font-size: 13px; opacity: 0.6; margin-top: 4px; }
  .cta-arrow { font-size: 32px; font-weight: 300; opacity: 0.5; }
}

.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 24px;
}
.grid-item {
  background: #fff;
  border-radius: 14px;
  padding: 18px;
  .grid-icon {
    width: 40px; height: 40px;
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px;
    margin-bottom: 12px;
  }
  .icon-1 { background: #E1EFFF; }
  .icon-2 { background: #FFF1DD; }
  .icon-3 { background: #E3F8E8; }
  .icon-4 { background: #F4E5F7; }
  .grid-title { font-size: 16px; font-weight: 600; color: #1C1C1E; }
  .grid-desc { font-size: 12px; color: #8E8E93; margin-top: 2px; }
}

.section-title {
  font-size: 13px;
  color: #8E8E93;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 12px;
  font-weight: 500;
}
.symptoms { margin-bottom: 24px; }
.pill-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.pill {
  padding: 8px 14px;
  background: #fff;
  border-radius: 16px;
  font-size: 13px;
  color: #1C1C1E;
}

.tabbar-placeholder { height: 100px; }
</style>
