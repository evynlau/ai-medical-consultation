<template>
  <view class="history-page">
    <view class="empty" v-if="!loading && !list.length">
      <view class="empty-icon">💬</view>
      <view class="empty-title">暂无问诊记录</view>
      <view class="empty-desc">去开启第一次问诊吧</view>
      <view class="btn" @click="goChat" style="margin-top:20px; display:inline-flex; width:auto; padding:0 24px">开始问诊</view>
    </view>

    <view v-else class="list">
      <view
        v-for="item in list"
        :key="item.id"
        class="card-item"
        @click="openDetail(item)"
      >
        <view class="card-row1">
          <view class="complaint truncate">{{ item.chief_complaint || '(无主诉)' }}</view>
          <view v-if="item.urgency_level" class="tag" :class="`urgency-${item.urgency_level}`">
            {{ urgencyLabel(item.urgency_level) }}
          </view>
        </view>
        <view class="card-row2">
          <view v-if="item.recommended_department" class="dept">
            <text class="dept-icon">🏥</text> {{ item.recommended_department }}
          </view>
          <view class="time">{{ formatTime(item.created_at) }}</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/api/index.js'

const list = ref([])
const loading = ref(true)

const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${(d.getMonth()+1).toString().padStart(2,'0')}-${d.getDate().toString().padStart(2,'0')} ${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}`
}
const urgencyLabel = (l) => ['', '无需就医', '择期就医', '尽快就医', '立即急诊'][l || 1]
const goChat = () => uni.switchTab({ url: '/pages/chat/chat' })
const openDetail = (item) => {
  // 复用 chat 页
  uni.navigateTo({ url: `/pages/chat/chat?id=${item.id}` })
}

const load = async () => {
  loading.value = true
  try {
    const data = await api.listConsultations({ limit: 50, offset: 0 })
    list.value = Array.isArray(data) ? data : (data.items || data.results || [])
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.history-page {
  min-height: 100vh;
  background: #F2F2F7;
  padding: 16px;
}
.empty {
  text-align: center;
  padding: 80px 0;
  .empty-icon { font-size: 48px; }
  .empty-title { font-size: 17px; color: #3C3C43; margin-top: 12px; font-weight: 500; }
  .empty-desc { font-size: 13px; color: #8E8E93; margin-top: 4px; }
}
.list { display: flex; flex-direction: column; gap: 12px; }
.card-item {
  background: #fff;
  border-radius: 14px;
  padding: 16px;
}
.card-row1 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.complaint {
  flex: 1;
  font-size: 16px;
  color: #1C1C1E;
  font-weight: 500;
}
.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-row2 {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #8E8E93;
}
.dept { display: flex; align-items: center; gap: 4px; }
.dept-icon { font-size: 12px; }
.tag {
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  &.urgency-1, &.urgency-2 { background: #E3F8E8; color: #1B7F36; }
  &.urgency-3 { background: #FFF1DD; color: #B25E00; }
  &.urgency-4 { background: #FFE5E3; color: #FF3B30; }
}
</style>
