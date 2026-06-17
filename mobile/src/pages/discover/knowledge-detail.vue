<template>
  <view class="kb-detail">
    <view v-if="loading" class="loading">加载中…</view>
    <view v-else-if="data" class="content">
      <view class="title">{{ data.title }}</view>
      <view class="meta">
        <text class="tag">{{ catLabel(data.category) }}</text>
        <text v-if="data.source" class="source">来源:{{ data.source }}</text>
      </view>
      <view class="body">{{ data.content }}</view>
    </view>
    <view v-else class="loading">内容不存在</view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/api/index.js'

const data = ref(null)
const loading = ref(true)
const catLabel = (c) => ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c || '其他')

onMounted(async () => {
  const pages = getCurrentPages()
  const id = pages[pages.length - 1].options.id
  try {
    data.value = await api.getKnowledge(id)
  } finally {
    loading.value = false
  }
})
</script>

<style lang="scss" scoped>
.kb-detail { min-height: 100vh; background: #F2F2F7; padding: 16px; }
.content {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
  .title { font-size: 20px; font-weight: 700; color: #1C1C1E; margin-bottom: 8px; }
  .meta { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .tag { padding: 2px 8px; background: #E1EFFF; color: #0040A3; border-radius: 6px; font-size: 11px; }
  .source { font-size: 12px; color: #8E8E93; }
  .body { font-size: 15px; color: #1C1C1E; line-height: 1.7; white-space: pre-wrap; }
}
.loading { text-align: center; padding: 80px 0; color: #8E8E93; }
</style>
