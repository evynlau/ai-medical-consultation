<template>
  <view class="discover-page">
    <view class="status-bar" :style="{ height: statusBarHeight + 'px' }" />

    <view class="header">
      <view class="header-title">发现</view>
    </view>

    <view class="list">
      <view class="list-item" @click="go('/pages/discover/knowledge')">
        <view class="icon" style="background:#E3F8E8">📚</view>
        <view class="title">知识库</view>
        <view class="desc">医学指南 · 600+ 篇</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item" @click="go('/pages/discover/doctors')">
        <view class="icon" style="background:#F4E5F7">👨‍⚕️</view>
        <view class="title">名医录</view>
        <view class="desc">按科室找医生</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item" @click="go('/pages/discover/xray')">
        <view class="icon" style="background:#E1EFFF">🩻</view>
        <view class="title">胸片分析</view>
        <view class="desc">18 维病理识别</view>
        <text class="arrow">›</text>
      </view>
      <view class="list-item" @click="go('/pages/discover/ocr')">
        <view class="icon" style="background:#FFF1DD">📄</view>
        <view class="title">报告识别</view>
        <view class="desc">拍照即识别处方 / 报告</view>
        <text class="arrow">›</text>
      </view>
    </view>

    <view class="bottom-tip">⚠️ 所有信息仅供参考,不能替代专业医生诊断</view>

    <view class="tabbar-placeholder" />
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { getToken } from '@/api/index.js'

const statusBarHeight = ref(20)
try {
  statusBarHeight.value = uni.getSystemInfoSync().statusBarHeight || 20
} catch {}

const go = (url) => {
  if (!getToken() && (url.includes('xray') || url.includes('ocr'))) {
    return uni.showToast({ title: '请先登录', icon: 'none' })
  }
  uni.navigateTo({ url })
}
</script>

<style lang="scss" scoped>
.discover-page {
  min-height: 100vh;
  background: #F2F2F7;
}
.header {
  padding: 24px 16px 12px;
  .header-title {
    font-size: 28px;
    font-weight: 700;
    color: #1C1C1E;
  }
}
.list {
  margin: 16px;
  background: #fff;
  border-radius: 14px;
  overflow: hidden;
}
.list-item {
  display: flex;
  align-items: center;
  min-height: 64px;
  padding: 12px 16px;
  border-bottom: 0.5px solid #E5E5EA;
  &:last-child { border-bottom: none; }
  .icon {
    width: 36px; height: 36px;
    border-radius: 9px;
    margin-right: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 20px;
  }
  .title { flex: 1; font-size: 16px; color: #1C1C1E; font-weight: 500; }
  .desc { font-size: 13px; color: #8E8E93; }
  .arrow { color: #C7C7CC; font-size: 22px; font-weight: 300; }
}
.bottom-tip {
  text-align: center;
  font-size: 12px;
  color: #8E8E93;
  padding: 32px 16px;
}
.tabbar-placeholder { height: 100px; }
</style>
