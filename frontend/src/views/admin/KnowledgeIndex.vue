<!--
  KnowledgeIndex - 知识库索引管理
  - 启动期不再自动向量化,所有 embedding 都在这里显式触发
  - 展示当前索引状态(条数/签名/大小/时间)
  - 重建索引按钮调用现有 POST /admin/reindex
  - 轮询 /admin/reindex/status 拿实时进度
-->
<template>
  <div class="knowledge-index">
    <PageHero
      badge="管理端操作 · 影响所有用户搜索"
      title="知识库索引"
      subtitle="RAG 检索依赖本地 FAISS 索引。启动期不再自动构建,任何修改后请在此手动触发重建。"
      :icon="Cpu"
      :variant="1"
    />

    <el-row :gutter="16">
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="info-card">
          <template #header>
            <div class="card-head">
              <span><el-icon><DataLine /></el-icon> 索引状态</span>
              <el-button :icon="Refresh" size="small" @click="loadInfo" :loading="loadingInfo">
                刷新
              </el-button>
            </div>
          </template>

          <el-skeleton v-if="loadingInfo && !info" :rows="6" animated />

          <div v-else-if="info" class="info-grid">
            <div class="info-row">
              <span class="lbl">磁盘索引</span>
              <el-tag v-if="info.exists" type="success" size="small">存在</el-tag>
              <el-tag v-else type="danger" size="small">不存在</el-tag>
            </div>
            <div class="info-row">
              <span class="lbl">向量条数</span>
              <span class="val" :class="{ 'val-zero': info.ntotal === 0 }">
                {{ info.ntotal }} 条
              </span>
            </div>
            <div class="info-row">
              <span class="lbl">文档签名</span>
              <span class="val mono">
                <template v-if="info.has_signature">{{ info.signature || '—' }}</template>
                <template v-else><el-tag type="warning" size="small">旧版无签名</el-tag></template>
              </span>
            </div>
            <div class="info-row">
              <span class="lbl">索引文件</span>
              <span class="val">{{ info.index_size_mb }} MB</span>
            </div>
            <div class="info-row">
              <span class="lbl">元数据文件</span>
              <span class="val">{{ info.metadata_size_kb }} KB</span>
            </div>
            <div class="info-row">
              <span class="lbl">最后构建</span>
              <span class="val">{{ info.mtime || '—' }}</span>
            </div>
          </div>

          <el-alert
            v-if="info && info.ntotal === 0"
            type="warning"
            :closable="false"
            show-icon
            style="margin-top: 12px"
            title="索引为空 — 搜索会返回空结果"
            description="点击右下「重建索引」按钮,系统会读取数据库 + 知识库 .md + 名医录,生成 FAISS 索引(预计 3-5 分钟)。"
          />
        </el-card>
      </el-col>

      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="action-card">
          <template #header>
            <span><el-icon><Operation /></el-icon> 操作</span>
          </template>

          <div class="action-stack">
            <el-button
              type="primary"
              size="large"
              :icon="MagicStick"
              :loading="status === 'running' || status === 'queued'"
              :disabled="status === 'running' || status === 'queued'"
              @click="handleRebuild"
              class="action-btn"
            >
              重建索引
            </el-button>
            <div class="action-hint">
              重新读取数据库 + .md + 名医录,生成新索引覆盖磁盘。<br>
              完成后 <strong>无需重启</strong>,管理后台 / 问诊页立即生效。
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 进度区 -->
    <el-card v-if="status && status !== 'idle'" shadow="never" class="progress-card">
      <template #header>
        <div class="card-head">
          <span>
            <el-icon v-if="status === 'running' || status === 'queued'"><Loading /></el-icon>
            <el-icon v-else-if="status === 'finished'"><CircleCheck /></el-icon>
            <el-icon v-else-if="status === 'error'"><CircleClose /></el-icon>
            重建进度
          </span>
          <el-tag
            :type="statusType"
            size="small"
            effect="dark"
          >{{ statusLabel }}</el-tag>
        </div>
      </template>

      <div v-if="status === 'running' || status === 'queued'">
        <el-progress
          :percentage="progressPct"
          :status="status === 'queued' ? 'warning' : undefined"
          :stroke-width="14"
        />
        <div class="progress-meta">
          累计 {{ progress.current }} / {{ progress.total }} 条
          <span v-if="progress.started_at" class="muted">
            · 已用 {{ elapsed }}s
          </span>
        </div>
      </div>

      <el-result
        v-else-if="status === 'finished'"
        icon="success"
        :title="`索引重建完成:${progress.current} 条`"
        sub-title="现在问诊页 / 知识库页的搜索将使用新索引"
      >
        <template #extra>
          <el-button type="primary" @click="loadInfo">刷新状态</el-button>
        </template>
      </el-result>

      <el-result
        v-else-if="status === 'error'"
        icon="error"
        title="重建失败"
        :sub-title="progress.error || '未知错误'"
      >
        <template #extra>
          <el-button @click="handleRebuild" type="primary">重试</el-button>
        </template>
      </el-result>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh, MagicStick, DataLine, Operation,
  Loading, CircleCheck, CircleClose, Cpu,
} from '@element-plus/icons-vue'
import { adminApi } from '@/api/admin'
import PageHero from '@/components/PageHero.vue'

const info = ref(null)
const loadingInfo = ref(false)
const status = ref('idle')
const progress = ref({ current: 0, total: 0, started_at: null, finished_at: null, error: null })
let pollTimer = null

const statusType = computed(() => ({
  idle: 'info', queued: 'warning', running: 'primary',
  finished: 'success', error: 'danger',
}[status.value] || 'info'))

const statusLabel = computed(() => ({
  idle: '空闲', queued: '排队中', running: '运行中',
  finished: '完成', error: '失败',
}[status.value] || status.value))

const progressPct = computed(() => {
  if (progress.value.total === 0) return 0
  return Math.min(100, Math.round(progress.value.current / progress.value.total * 100))
})

const elapsed = computed(() => {
  if (!progress.value.started_at) return 0
  const end = progress.value.finished_at || Date.now() / 1000
  return Math.max(0, Math.round(end - progress.value.started_at))
})

const loadInfo = async () => {
  loadingInfo.value = true
  try {
    info.value = await adminApi.reindexInfo()
  } catch (e) {
    ElMessage.error('加载索引信息失败')
  } finally {
    loadingInfo.value = false
  }
}

const loadStatus = async () => {
  try {
    const r = await adminApi.reindexStatus()
    status.value = r.status
    progress.value = r.progress
    if (r.status === 'finished' || r.status === 'error') {
      stopPoll()
      if (r.status === 'finished') loadInfo()
    }
  } catch {}
}

const startPoll = () => {
  stopPoll()
  pollTimer = setInterval(loadStatus, 1000)
}
const stopPoll = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const handleRebuild = async () => {
  try {
    await ElMessageBox.confirm(
      '重建会读取所有文档(数据库 + .md 文件 + 名医录)并重新向量化,'
      + '过程约需 3-5 分钟。期间不影响当前服务的搜索(继续用旧索引,'
      + '完成后再切换)。',
      '确认重建索引',
      { type: 'warning', confirmButtonText: '开始重建' }
    )
  } catch { return }
  try {
    const r = await adminApi.reindexAsync()
    status.value = r.status
    progress.value = r.progress || progress.value
    ElMessage.success('已提交,后台开始向量化...')
    startPoll()
  } catch (e) {
    ElMessage.error('提交失败')
  }
}

onMounted(async () => {
  await Promise.all([loadInfo(), loadStatus()])
  if (status.value === 'running' || status.value === 'queued') startPoll()
})

onUnmounted(stopPoll)
</script>

<style lang="scss" scoped>
@use '@/styles/tokens.scss' as t;

.knowledge-index {
  max-width: 1200px;
  margin: 0 auto;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
  }
}

.info-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed t.c('border');

  &:last-child { border-bottom: none; }

  .lbl {
    color: t.c('text-3');
    font-size: 13px;
    min-width: 90px;
  }
  .val {
    color: t.c('text-1');
    font-size: 14px;
    font-weight: 500;
    &.val-zero { color: t.c('danger'); }
    &.mono { font-family: var(--font-mono); font-size: 13px; }
  }
}

.action-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.action-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex: 1;
  justify-content: center;
}
.action-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
}
.action-hint {
  color: t.c('text-3');
  font-size: 13px;
  line-height: 1.6;
  strong { color: t.c('primary-700'); }
}

.progress-card {
  margin-top: 16px;
}
.progress-meta {
  margin-top: 8px;
  font-size: 13px;
  color: t.c('text-2');
  .muted { color: t.c('text-3'); margin-left: 4px; }
}

@media (max-width: 720px) {
  .action-card { margin-top: 16px; }
}
</style>
