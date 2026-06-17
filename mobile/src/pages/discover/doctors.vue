<template>
  <view class="doctors-page">
    <view v-if="loading" class="loading">加载中…</view>
    <view v-else-if="!list.length" class="empty">暂无名医</view>
    <view v-else class="list">
      <view v-for="d in list" :key="d.id" class="card">
        <view class="row1">
          <view class="avatar">{{ (d.name || '?').charAt(0) }}</view>
          <view class="info">
            <view class="name">
              {{ d.name }}
              <text v-if="d.title" class="title-tag">{{ d.title }}</text>
            </view>
            <view class="hospital">{{ d.hospital }}</view>
            <view class="dept">{{ d.department }}</view>
          </view>
        </view>
        <view v-if="d.diseases" class="diseases">
          <text class="lbl">擅长:</text>
          <text>{{ d.diseases }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '@/api/index.js'

const list = ref([])
const loading = ref(false)

const load = async () => {
  loading.value = true
  try {
    const data = await api.listDoctors({ limit: 50, offset: 0 })
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
.doctors-page { min-height: 100vh; background: #F2F2F7; padding: 12px 16px; }
.list { display: flex; flex-direction: column; gap: 12px; }
.card {
  background: #fff;
  border-radius: 14px;
  padding: 14px;
}
.row1 { display: flex; gap: 12px; margin-bottom: 10px; }
.avatar {
  width: 48px; height: 48px;
  border-radius: 50%;
  background: #1C1C1E;
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 500;
  flex-shrink: 0;
}
.info { flex: 1; }
.name { font-size: 16px; font-weight: 600; color: #1C1C1E; }
.title-tag {
  margin-left: 6px;
  padding: 1px 6px;
  background: #FFF1DD;
  color: #B25E00;
  font-size: 11px;
  border-radius: 4px;
  font-weight: 400;
}
.hospital { font-size: 13px; color: #3C3C43; margin-top: 2px; }
.dept { font-size: 12px; color: #8E8E93; margin-top: 2px; }
.diseases {
  font-size: 13px;
  color: #3C3C43;
  background: #F2F2F7;
  padding: 8px 12px;
  border-radius: 8px;
  .lbl { color: #8E8E93; margin-right: 4px; }
}

.loading, .empty { text-align: center; padding: 60px 0; color: #8E8E93; }
</style>
