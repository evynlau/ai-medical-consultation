<template>
  <div class="history page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3><el-icon><Clock /></el-icon> 我的问诊记录</h3>
          <el-button type="primary" @click="$router.push('/chat')">新问诊</el-button>
        </div>
      </template>

      <template v-if="loading">
        <el-skeleton :rows="5" animated />
      </template>

      <template v-else-if="!list.length">
        <el-empty description="暂无问诊记录,去开启第一次问诊吧" />
      </template>

      <template v-else>
        <el-table :data="list" stripe style="width: 100%" @row-click="openDetail">
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="主诉" prop="chief_complaint" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="complaint">{{ row.chief_complaint }}</span>
            </template>
          </el-table-column>
          <el-table-column label="紧急程度" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.urgency_level" :type="urgencyType(row.urgency_level)" size="small">
                {{ urgencyLabel(row.urgency_level) }}
              </el-tag>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column label="推荐科室" prop="recommended_department" width="140" />
          <el-table-column label="消息数" prop="message_count" width="80" align="center" />
          <el-table-column label="状态" prop="status" width="80">
            <template #default="{ row }">
              <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                {{ row.status === 'active' ? '进行中' : '已结束' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="时间" width="170">
            <template #default="{ row }">
              {{ formatTime(row.created_at) }}
            </template>
          </el-table-column>
        </el-table>

        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          class="pagination"
          @current-change="load"
          @size-change="load"
        />
      </template>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'
import { consultApi } from '@/api/consult'

const router = useRouter()
const chatStore = useChatStore()
const list = ref([])
const loading = ref(true)
const pagination = reactive({ page: 1, size: 20, total: 0 })

const formatTime = (iso) => {
  if (!iso) return ''
  return new Date(iso).toLocaleString('zh-CN', { hour12: false })
}
const urgencyLabel = (l) => ['', '无需就医', '择期就医', '尽快就医', '立即急诊'][l || 1]
const urgencyType = (l) => ['', 'info', 'success', 'warning', 'danger'][l || 1]

const load = async () => {
  loading.value = true
  try {
    const res = await consultApi.list({
      limit: pagination.size,
      offset: (pagination.page - 1) * pagination.size
    })
    list.value = res
    if (res.length < pagination.size) {
      pagination.total = (pagination.page - 1) * pagination.size + res.length
    } else {
      pagination.total = pagination.page * pagination.size + 1
    }
  } catch {
    ElMessage.error('加载问诊记录失败')
  } finally {
    loading.value = false
  }
}

const openDetail = (row) => {
  router.push(`/history/${row.id}`)
}

onMounted(load)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
}
.pagination { margin-top: 16px; justify-content: flex-end; display: flex; }
.complaint { color: #303133; }
:deep(.el-table__row) { cursor: pointer; }
</style>
