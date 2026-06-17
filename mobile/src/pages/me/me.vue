<template>
  <view class="me-page">
    <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />

    <!-- 头部用户信息 -->
    <view class="profile">
      <view class="profile-left">
        <view class="avatar">{{ avatarText }}</view>
        <view class="profile-info">
          <view v-if="isLogin" class="name">{{ user.nickname || user.username || '用户' }}</view>
          <view v-else class="name">未登录</view>
          <view v-if="isLogin" class="phone">{{ maskPhone(user.phone) }}</view>
          <view v-else class="phone" @click="goLogin">点击登录</view>
        </view>
      </view>
      <view v-if="isLogin" class="profile-action" @click="handleLogout">退出</view>
    </view>

    <!-- 统计卡(Apple Health 风格) -->
    <view v-if="isLogin" class="stats">
      <view class="stat">
        <view class="stat-num">{{ stats.consultations }}</view>
        <view class="stat-lbl">问诊</view>
      </view>
      <view class="stat">
        <view class="stat-num">{{ stats.xray }}</view>
        <view class="stat-lbl">胸片分析</view>
      </view>
      <view class="stat">
        <view class="stat-num">{{ stats.ocr }}</view>
        <view class="stat-lbl">报告识别</view>
      </view>
    </view>

    <!-- 功能列表 -->
    <view class="list">
      <view class="list-item" @click="go('/pages/me/history')">
        <view class="icon" style="background:#E1EFFF">💬</view>
        <view class="title">问诊记录</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item">
        <view class="icon" style="background:#F4E5F7">👤</view>
        <view class="title">个人资料</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item">
        <view class="icon" style="background:#E3F8E8">🔒</view>
        <view class="title">隐私与安全</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item">
        <view class="icon" style="background:#FFF1DD">❓</view>
        <view class="title">帮助与反馈</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item">
        <view class="icon" style="background:#F2F2F7; color:#8E8E93">ⓘ</view>
        <view class="title">关于</view>
        <view class="desc">v1.0.0</view>
        <text class="arrow">›</text>
      </view>
    </view>

    <view class="tabbar-placeholder" />
  </view>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getUser, getToken, clearAuth, api } from '@/api/index.js'

const statusBarHeight = ref(20)
try {
  statusBarHeight.value = uni.getSystemInfoSync().statusBarHeight || 20
} catch {}

const user = ref(getUser() || {})
const isLogin = computed(() => !!getToken())
const stats = ref({ consultations: 0, xray: 0, ocr: 0 })

const avatarText = computed(() => {
  const name = user.value.nickname || user.value.username || '?'
  return name.charAt(0).toUpperCase()
})

const maskPhone = (p) => {
  if (!p) return ''
  return p.length === 11 ? `${p.slice(0,3)}****${p.slice(7)}` : p
}

const go = (url) => {
  if (!isLogin.value) return uni.navigateTo({ url: '/pages/login/login' })
  uni.navigateTo({ url })
}
const goLogin = () => uni.navigateTo({ url: '/pages/login/login' })

const handleLogout = () => {
  uni.showModal({
    title: '确认退出',
    content: '退出后需要重新登录',
    success: (res) => {
      if (res.confirm) {
        clearAuth()
        uni.reLaunch({ url: '/pages/home/home' })
      }
    },
  })
}

const loadStats = async () => {
  if (!isLogin.value) return
  try {
    const list = await api.listConsultations({ limit: 1, offset: 0 })
    stats.value.consultations = list.length > 0 ? list.total || list.length : 0
  } catch {}
}

onMounted(loadStats)
</script>

<style lang="scss" scoped>
.me-page {
  min-height: 100vh;
  background: #F2F2F7;
}

.profile {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24px 16px 16px;
  background: #fff;
  margin-bottom: 12px;
}
.profile-left { display: flex; align-items: center; gap: 14px; }
.avatar {
  width: 60px; height: 60px;
  border-radius: 50%;
  background: #1C1C1E;
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; font-weight: 500;
}
.name { font-size: 18px; font-weight: 600; color: #1C1C1E; }
.phone { font-size: 13px; color: #8E8E93; margin-top: 2px; }
.profile-action {
  padding: 6px 14px;
  border: 0.5px solid #C7C7CC;
  color: #3C3C43;
  border-radius: 14px;
  font-size: 13px;
}

.stats {
  display: flex;
  background: #fff;
  margin: 0 16px 16px;
  border-radius: 14px;
  padding: 16px 0;
}
.stat {
  flex: 1;
  text-align: center;
  border-right: 0.5px solid #E5E5EA;
  &:last-child { border-right: none; }
  .stat-num { font-size: 22px; font-weight: 700; color: #1C1C1E; }
  .stat-lbl { font-size: 12px; color: #8E8E93; margin-top: 2px; }
}

.list {
  margin: 0 16px;
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
}
.list-item {
  display: flex;
  align-items: center;
  min-height: 56px;
  padding: 12px 16px;
  border-bottom: 0.5px solid #E5E5EA;
  &:last-child { border-bottom: none; }
  .icon {
    width: 32px; height: 32px;
    border-radius: 8px;
    margin-right: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px;
  }
  .title { flex: 1; font-size: 16px; color: #1C1C1E; }
  .desc { font-size: 13px; color: #8E8E93; }
  .arrow { color: #C7C7CC; font-size: 20px; font-weight: 300; }
}

.tabbar-placeholder { height: 100px; }
</style>
