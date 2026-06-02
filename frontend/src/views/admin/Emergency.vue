<template>
  <div class="emergency">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3>
            <el-icon color="#f56c6c"><WarningFilled /></el-icon>
            紧急病例看板
            <el-tag type="danger" size="small" style="margin-left: 8px">urgency ≥ 4</el-tag>
          </h3>
          <div class="filters">
            <el-radio-group v-model="filterActive" @change="load">
              <el-radio-button :value="true">进行中</el-radio-button>
              <el-radio-button :value="false">全部</el-radio-button>
            </el-radio-group>
            <el-button @click="load">刷新</el-button>
          </div>
        </div>
      </template>

      <el-empty v-if="!loading && list.length === 0" description="🎉 当前没有紧急病例" />

      <div v-loading="loading" class="emergency-grid">
        <el-card
          v-for="item in list"
          :key="item.id"
          class="emergency-card"
          shadow="hover"
          :class="'urgency-' + item.urgency_level"
        >
          <div class="card-top">
            <div class="urgency-badge">
              <el-icon :size="20"><WarningFilled /></el-icon>
              <span>{{ urgencyLabel(item.urgency_level) }}</span>
            </div>
            <el-tag size="small" :type="item.status === 'active' ? 'success' : 'info'">
              {{ item.status === 'active' ? '进行中' : '已结束' }}
            </el-tag>
          </div>
          <div class="complaint">{{ item.chief_complaint }}</div>
          <div class="meta">
            <span><el-icon><Files /></el-icon> {{ item.recommended_department || '未识别科室' }}</span>
            <span style="margin-left: 12px"><el-icon><Clock /></el-icon> {{ formatTime(item.created_at) }}</span>
          </div>
          <div class="actions">
            <el-button type="primary" size="small" @click="$router.push(`/admin/consultations?focus=${item.id}`)">
              立即处理
            </el-button>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { adminApi } from '@/api/admin'

const list = ref([])
const loading = ref(false)
const filterActive = ref(true)

const formatTime = (iso) => new Date(iso).toLocaleString('zh-CN', { hour12: false })
const urgencyLabel = (l) => ['', '无需就医', '择期就医', '尽快就医', '立即急诊'][l || 1]

const load = async () => {
  loading.value = true
  try {
    list.value = await adminApi.emergency({ only_active: filterActive.value, limit: 50 })
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
  .filters { display: flex; gap: 12px; align-items: center; }
}
.emergency-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}
.emergency-card {
  border-left: 4px solid #f56c6c;
  &.urgency-4 { border-left-color: #f56c6c; }
  &.urgency-3 { border-left-color: #E6A23C; }
  .card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .urgency-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #f56c6c;
    font-weight: 600;
  }
  .complaint {
    font-size: 14px;
    color: #303133;
    line-height: 1.5;
    margin: 8px 0;
    min-height: 42px;
  }
  .meta {
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
    span { display: inline-flex; align-items: center; gap: 4px; }
  }
  .actions { text-align: right; }
}
</style>
