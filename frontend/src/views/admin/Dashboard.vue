<template>
  <div class="dashboard">
    <h2 class="page-title">
      <el-icon><DataAnalysis /></el-icon>
      数据概览
    </h2>

    <el-row :gutter="16" v-loading="loading">
      <!-- 概览卡片 -->
      <el-col :xs="12" :sm="8" :md="6" v-for="card in overviewCards" :key="card.key">
        <el-card class="stat-card" :body-style="{ padding: '16px' }">
          <div class="stat-icon" :style="{ background: card.bg }">
            <el-icon :size="24" color="#fff"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ card.value }}</div>
            <div class="stat-label">{{ card.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 紧急病例警示 -->
    <el-alert
      v-if="stats?.urgent?.pending > 0"
      class="urgent-alert"
      type="error"
      show-icon
      :closable="false"
    >
      <template #title>
        ⚠️ 当前有 <strong>{{ stats.urgent.pending }}</strong> 个紧急病例未处理(urgency ≥ 4)
        <el-button type="primary" size="small" @click="$router.push('/admin/emergency')" style="margin-left: 12px">
          立即查看 →
        </el-button>
      </template>
    </el-alert>

    <el-row :gutter="16" style="margin-top: 16px">
      <!-- 7 日趋势 -->
      <el-col :xs="24" :md="14">
        <el-card>
          <template #header>
            <span><el-icon><TrendCharts /></el-icon> 近 7 天问诊量</span>
          </template>
          <div class="trend">
            <div v-for="(d, i) in stats?.consultation_trend_7d || []" :key="i" class="trend-bar">
              <div class="bar" :style="{ height: Math.max(8, d.count * 30) + 'px' }">
                <span class="bar-value">{{ d.count }}</span>
              </div>
              <div class="bar-date">{{ d.date }}</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 知识库分布 -->
      <el-col :xs="24" :md="10">
        <el-card>
          <template #header>
            <span><el-icon><Reading /></el-icon> 知识库分布</span>
          </template>
          <div class="kb-dist">
            <div v-for="(count, cat) in stats?.knowledge_distribution || {}" :key="cat" class="kb-row">
              <el-tag :type="categoryType(cat)">{{ categoryLabel(cat) }}</el-tag>
              <div class="kb-bar-bg">
                <div class="kb-bar-fg" :style="{ width: barWidth(count) + '%' }"></div>
              </div>
              <span class="kb-count">{{ count }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'

const stats = ref(null)
const loading = ref(false)

const overviewCards = ref([])

const categoryLabel = (c) => ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c)
const categoryType = (c) => ({ disease: 'danger', drug: 'warning', examination: 'success', guideline: 'info' }[c] || '')

const barWidth = (count) => {
  const total = Object.values(stats.value?.knowledge_distribution || {}).reduce((a, b) => a + b, 0) || 1
  return Math.round((count / total) * 100)
}

const load = async () => {
  loading.value = true
  try {
    stats.value = await adminApi.stats()
    const o = stats.value.overview
    const t = stats.value.today
    const w = stats.value.week
    overviewCards.value = [
      { key: 'users', label: '总用户数', value: o.total_users, icon: 'User', bg: 'linear-gradient(135deg, #409EFF, #2c7be5)' },
      { key: 'cons', label: '总问诊数', value: o.total_consultations, icon: 'ChatLineSquare', bg: 'linear-gradient(135deg, #67C23A, #5daf34)' },
      { key: 'active', label: '进行中', value: o.active_consultations, icon: 'Loading', bg: 'linear-gradient(135deg, #E6A23C, #cf9236)' },
      { key: 'today', label: '今日新增', value: t.new_consultations, icon: 'Calendar', bg: 'linear-gradient(135deg, #F56C6C, #dd6161)' },
      { key: 'urgent', label: '紧急病例', value: stats.value.urgent.total, icon: 'WarningFilled', bg: 'linear-gradient(135deg, #ff6b6b, #ee5a52)' },
      { key: 'pending', label: '待处理紧急', value: stats.value.urgent.pending, icon: 'BellFilled', bg: 'linear-gradient(135deg, #909399, #82848a)' },
      { key: 'week', label: '本周问诊', value: w.new_consultations, icon: 'TrendCharts', bg: 'linear-gradient(135deg, #9b59b6, #8e44ad)' },
      { key: 'kb', label: '知识条目', value: o.total_knowledge, icon: 'Reading', bg: 'linear-gradient(135deg, #16a085, #1abc9c)' }
    ]
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
.page-title {
  font-size: 20px;
  margin: 0 0 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.stat-card {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  border-radius: 8px;
  .stat-icon {
    width: 48px;
    height: 48px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .stat-info {
    margin-left: 12px;
    flex: 1;
    .stat-value {
      font-size: 24px;
      font-weight: 600;
      color: #303133;
    }
    .stat-label {
      font-size: 12px;
      color: #909399;
      margin-top: 2px;
    }
  }
}
.urgent-alert {
  margin: 16px 0;
}
.trend {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  height: 200px;
  padding: 0 8px;
  .trend-bar {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;
    .bar {
      width: 32px;
      background: linear-gradient(180deg, #409EFF, #2c7be5);
      border-radius: 4px 4px 0 0;
      display: flex;
      align-items: flex-start;
      justify-content: center;
      padding-top: 4px;
      transition: height 0.3s;
      .bar-value { color: #fff; font-size: 11px; }
    }
    .bar-date { font-size: 12px; color: #909399; margin-top: 6px; }
  }
}
.kb-dist {
  .kb-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
    .kb-bar-bg {
      flex: 1;
      height: 12px;
      background: #f0f2f5;
      border-radius: 6px;
      overflow: hidden;
    }
    .kb-bar-fg {
      height: 100%;
      background: linear-gradient(90deg, #409EFF, #2c7be5);
      transition: width 0.3s;
    }
    .kb-count {
      width: 30px;
      text-align: right;
      color: #606266;
      font-size: 14px;
    }
  }
}
</style>
