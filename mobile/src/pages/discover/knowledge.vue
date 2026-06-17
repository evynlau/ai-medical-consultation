<template>
  <view class="kb-page">
    <!-- 搜索框 -->
    <view class="search-bar">
      <view class="search-input">
        <text class="search-icon">🔍</text>
        <input
          v-model="keyword"
          class="search-field"
          placeholder="搜索症状 / 疾病 / 药品"
          @confirm="onSearch"
        />
      </view>
    </view>

    <!-- 分类标签 -->
    <scroll-view class="tags" scroll-x>
      <view
        v-for="t in categories"
        :key="t.value"
        class="tag"
        :class="{ active: currentCat === t.value }"
        @click="currentCat = t.value; load()"
      >{{ t.label }}</view>
    </scroll-view>

    <!-- 列表 -->
    <view v-if="loading" class="loading">加载中…</view>
    <view v-else-if="!list.length" class="empty">暂无内容</view>
    <view v-else class="list">
      <view v-for="item in list" :key="item.id" class="card" @click="open(item)">
        <view class="title">{{ item.title }}</view>
        <view class="meta">
          <text class="tag-small" :class="`cat-${item.category}`">{{ catLabel(item.category) }}</text>
          <text v-if="item.tags" class="tags-text">{{ item.tags }}</text>
        </view>
        <view class="desc">{{ truncate(item.content, 80) }}</view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/api/index.js'

const keyword = ref('')
const currentCat = ref('')
const list = ref([])
const loading = ref(false)

const categories = [
  { value: '', label: '全部' },
  { value: 'disease', label: '疾病' },
  { value: 'drug', label: '药品' },
  { value: 'examination', label: '检查' },
  { value: 'guideline', label: '指南' },
]

const catLabel = (c) => ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c || '其他')
const truncate = (s, n) => s && s.length > n ? s.slice(0, n) + '...' : s
const open = (item) => uni.navigateTo({ url: `/pages/discover/knowledge-detail?id=${item.id}` })

const load = async () => {
  loading.value = true
  try {
    if (keyword.value.trim()) {
      list.value = await api.searchKnowledge(keyword.value.trim())
    } else {
      const params = { limit: 50, offset: 0 }
      if (currentCat.value) params.category = currentCat.value
      const data = await api.listKnowledge(params)
      list.value = Array.isArray(data) ? data : (data.items || data.results || [])
    }
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}
const onSearch = () => load()

onMounted(load)
</script>

<style lang="scss" scoped>
.kb-page {
  min-height: 100vh;
  background: #F2F2F7;
}
.search-bar {
  padding: 12px 16px;
  background: #fff;
  border-bottom: 0.5px solid #E5E5EA;
}
.search-input {
  display: flex;
  align-items: center;
  background: #F2F2F7;
  border-radius: 10px;
  padding: 0 12px;
  height: 36px;
  .search-icon { font-size: 14px; color: #8E8E93; margin-right: 6px; }
  .search-field { flex: 1; font-size: 15px; color: #1C1C1E; }
}

.tags {
  white-space: nowrap;
  padding: 12px 16px;
  background: #fff;
  border-bottom: 0.5px solid #E5E5EA;
}
.tag {
  display: inline-block;
  padding: 4px 14px;
  margin-right: 8px;
  background: #F2F2F7;
  color: #3C3C43;
  border-radius: 14px;
  font-size: 13px;
  &.active { background: #1C1C1E; color: #fff; }
}

.list { padding: 12px 16px; }
.card {
  background: #fff;
  border-radius: 14px;
  padding: 14px;
  margin-bottom: 12px;
  .title { font-size: 16px; font-weight: 600; color: #1C1C1E; margin-bottom: 6px; }
  .meta { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
  .tag-small {
    padding: 1px 6px; border-radius: 4px; font-size: 11px;
    &.cat-disease { background: #FFE5E3; color: #FF3B30; }
    &.cat-drug { background: #FFF1DD; color: #B25E00; }
    &.cat-examination { background: #E3F8E8; color: #1B7F36; }
    &.cat-guideline { background: #E1EFFF; color: #0040A3; }
  }
  .tags-text { font-size: 12px; color: #8E8E93; }
  .desc { font-size: 13px; color: #3C3C43; line-height: 1.5; }
}

.loading, .empty {
  text-align: center;
  padding: 60px 0;
  color: #8E8E93;
  font-size: 14px;
}
</style>
