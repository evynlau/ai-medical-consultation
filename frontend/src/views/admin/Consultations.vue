<template>
  <div class="admin-consultations">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3><el-icon><ChatLineSquare /></el-icon> 问诊管理</h3>
          <div class="filters">
            <el-input
              v-model="filters.keyword"
              placeholder="搜索主诉/诊断"
              clearable
              style="width: 200px"
              @keydown.enter="load"
            />
            <el-select v-model="filters.urgency" placeholder="紧急度" clearable style="width: 120px" @change="load">
              <el-option label="全部紧急度" :value="null" />
              <el-option label="紧急(4)" :value="4" />
              <el-option label="高(3)" :value="3" />
              <el-option label="中(2)" :value="2" />
              <el-option label="低(1)" :value="1" />
            </el-select>
            <el-select v-model="filters.status" placeholder="状态" clearable style="width: 110px" @change="load">
              <el-option label="全部状态" :value="null" />
              <el-option label="进行中" value="active" />
              <el-option label="已结束" value="closed" />
            </el-select>
            <el-button type="primary" @click="load">查询</el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe @row-click="openDetail">
        <el-table-column label="ID" prop="id" width="60" />
        <el-table-column label="主诉" prop="chief_complaint" min-width="200" show-overflow-tooltip />
        <el-table-column label="紧急度" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.urgency_level" :type="urgencyType(row.urgency_level)" size="small">
              {{ urgencyLabel(row.urgency_level) }}
            </el-tag>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column label="推荐科室" prop="recommended_department" width="130" />
        <el-table-column label="消息数" prop="message_count" width="80" align="center" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '进行中' : '已结束' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="openDetail(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" :title="`问诊详情 #${detail?.id || ''}`" width="900px" top="5vh">
      <div v-if="detail" v-loading="loadingDetail">
        <!-- 患者信息 -->
        <el-descriptions v-if="detail.user" :column="3" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="用户ID">{{ detail.user.id }}</el-descriptions-item>
          <el-descriptions-item label="用户名">{{ detail.user.username }}</el-descriptions-item>
          <el-descriptions-item label="性别">{{ detail.user.gender || '-' }}</el-descriptions-item>
          <el-descriptions-item label="年龄">{{ detail.user.age || '-' }}</el-descriptions-item>
          <el-descriptions-item label="过敏史" :span="2">{{ detail.user.allergies || '-' }}</el-descriptions-item>
          <el-descriptions-item label="慢性病" :span="3">{{ detail.user.chronic_diseases || '-' }}</el-descriptions-item>
        </el-descriptions>

        <el-descriptions :column="2" border size="small" style="margin-bottom: 12px">
          <el-descriptions-item label="主诉">{{ detail.chief_complaint }}</el-descriptions-item>
          <el-descriptions-item label="推荐科室">
            {{ detail.recommended_department || '-' }}
            <el-tag v-if="detail.urgency_level" :type="urgencyType(detail.urgency_level)" size="small" style="margin-left: 8px">
              紧急度 {{ detail.urgency_level }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.status === 'active' ? 'success' : 'info'" size="small">
              {{ detail.status === 'active' ? '进行中' : '已结束' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
        </el-descriptions>

        <!-- 对话消息 -->
        <h4>对话记录</h4>
        <div class="messages">
          <div
            v-for="m in detail.messages"
            :key="m.id"
            class="msg-item"
            :class="m.role"
          >
            <div class="msg-meta">
              <el-tag size="small" :type="roleType(m.role)">{{ roleLabel(m.role) }}</el-tag>
              <span v-if="m.urgency_level" :class="'urgency-' + m.urgency_level" style="margin-left: 6px">
                紧急度 {{ m.urgency_level }}
              </span>
              <span style="margin-left: auto; font-size: 12px; color: #909399">{{ formatTime(m.created_at) }}</span>
            </div>
            <div class="msg-content" v-html="renderContent(m.content)"></div>
          </div>
        </div>

        <!-- 医生回复表单 -->
        <el-divider v-if="detail.status === 'active'">医生回复</el-divider>
        <div v-if="detail.status === 'active'">
          <el-form label-width="100px">
            <el-form-item label="诊断意见">
              <el-input v-model="replyForm.diagnosis" placeholder="可选:补充诊断结论" />
            </el-form-item>
            <el-form-item label="覆盖紧急度">
              <el-radio-group v-model="replyForm.override_urgency">
                <el-radio :value="null">不覆盖</el-radio>
                <el-radio :value="4">紧急 (4)</el-radio>
                <el-radio :value="3">高 (3)</el-radio>
                <el-radio :value="2">中 (2)</el-radio>
                <el-radio :value="1">低 (1)</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="回复内容" required>
              <el-input v-model="replyForm.content" type="textarea" :rows="5"
                placeholder="请输入您的专业回复(将作为医生消息插入对话,并自动结束该问诊)" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="replying" @click="submitReply" :disabled="!replyForm.content.trim()">
                提交回复并结束问诊
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { adminApi } from '@/api/admin'

marked.setOptions({ breaks: true, gfm: true })

const list = ref([])
const loading = ref(false)
const filters = reactive({ keyword: '', urgency: null, status: null })
const formatTime = (iso) => iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'
const urgencyLabel = (l) => ['', '无需就医', '择期就医', '尽快就医', '立即急诊'][l || 1]
const urgencyType = (l) => ['', 'info', 'success', 'warning', 'danger'][l || 1]
const roleLabel = (r) => ({ user: '患者', assistant: 'AI', doctor: '医生', system: '系统' }[r] || r)
const roleType = (r) => ({ user: '', assistant: 'success', doctor: 'warning', system: 'info' }[r] || '')
const renderContent = (t) => t ? marked.parse(t) : ''

const load = async () => {
  loading.value = true
  try {
    list.value = await adminApi.consultations({
      keyword: filters.keyword || undefined,
      urgency: filters.urgency || undefined,
      status: filters.status || undefined
    })
  } catch (e) {
    ElMessage.error('加载问诊失败')
  } finally {
    loading.value = false
  }
}

const showDetail = ref(false)
const detail = ref(null)
const loadingDetail = ref(false)
const openDetail = async (row) => {
  showDetail.value = true
  loadingDetail.value = true
  try {
    detail.value = await adminApi.consultationDetail(row.id)
    replyForm.content = ''
    replyForm.diagnosis = ''
    replyForm.override_urgency = null
  } catch {
    ElMessage.error('加载详情失败')
  } finally {
    loadingDetail.value = false
  }
}

const replyForm = reactive({ content: '', diagnosis: '', override_urgency: null })
const replying = ref(false)
const submitReply = async () => {
  if (!replyForm.content.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  await ElMessageBox.confirm('提交后该问诊将自动标记为"已结束",确认?', '提示', { type: 'warning' })
  replying.value = true
  try {
    await adminApi.doctorReply(detail.value.id, {
      content: replyForm.content,
      diagnosis: replyForm.diagnosis || undefined,
      override_urgency: replyForm.override_urgency || undefined
    })
    ElMessage.success('回复成功,问诊已结束')
    showDetail.value = false
    load()
  } catch (e) {
    // 错误已由拦截器显示
  } finally {
    replying.value = false
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
  .filters { display: flex; gap: 8px; }
}
.messages {
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 6px;
}
.msg-item {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: #fff;
  border-radius: 6px;
  border-left: 3px solid #909399;
  &.user { border-left-color: #67C23A; }
  &.assistant { border-left-color: #409EFF; }
  &.doctor { border-left-color: #E6A23C; }
  &.system { border-left-color: #909399; opacity: 0.7; font-size: 13px; }
  .msg-meta { display: flex; align-items: center; margin-bottom: 6px; font-size: 13px; }
  .msg-content { line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
}
.urgency-4 { color: #f56c6c; font-weight: 600; }
:deep(.el-table__row) { cursor: pointer; }
</style>
