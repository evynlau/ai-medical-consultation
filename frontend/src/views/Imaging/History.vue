<!-- Imaging/History.vue - 历史分析记录 -->
<template>
  <div class="imaging-history page-container">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3>
            <el-icon><Clock /></el-icon>
            影像分析历史
          </h3>
          <el-button type="primary" @click="$router.push('/imaging')">
            <el-icon><Plus /></el-icon>
            新建分析
          </el-button>
        </div>
      </template>

      <template v-if="loading">
        <el-skeleton :rows="5" animated />
      </template>

      <template v-else-if="!list.length">
        <el-empty description="暂无分析记录" />
      </template>

      <template v-else>
        <el-table :data="list" stripe @row-click="viewDetail">
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="影像" width="80">
            <template #default="{ row }">
              <el-image
                v-if="row.gradcam"
                :src="row.gradcam"
                fit="cover"
                style="width: 50px; height: 50px; border-radius: 4px;"
                :preview-src-list="[row.gradcam]"
                preview-teleported
              />
              <el-avatar v-else shape="square" :size="50">
                <el-icon><Picture /></el-icon>
              </el-avatar>
            </template>
          </el-table-column>
          <el-table-column label="文件名" prop="image_filename" min-width="150" show-overflow-tooltip />
          <el-table-column label="AI 判断" width="120">
            <template #default="{ row }">
              <el-tag :type="row.prediction === 'NORMAL' ? 'success' : 'danger'" size="small">
                {{ row.prediction_label }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="120">
            <template #default="{ row }">
              <el-progress
                :percentage="Math.round(row.confidence * 100)"
                :stroke-width="10"
                :color="row.prediction === 'NORMAL' ? '#67c23a' : '#f56c6c'"
              />
            </template>
          </el-table-column>
          <el-table-column label="医生标注" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.annotation" size="small" type="info">已标注</el-tag>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column label="标注一致性" width="100">
            <template #default="{ row }">
              <el-tag
                v-if="row.doctor_agreement === true"
                type="success"
                size="small"
              >一致</el-tag>
              <el-tag
                v-else-if="row.doctor_agreement === false"
                type="warning"
                size="small"
              >不一致</el-tag>
              <span v-else style="color: #c0c4cc">-</span>
            </template>
          </el-table-column>
          <el-table-column label="分析时间" width="170">
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

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" :title="`分析详情 #${detail?.id || ''}`" width="800px">
      <div v-if="detail" v-loading="loadingDetail">
        <el-row :gutter="16">
          <el-col :span="12">
            <div class="detail-label">AI 判断</div>
            <el-tag :type="detail.prediction === 'NORMAL' ? 'success' : 'danger'" size="large">
              {{ detail.prediction_label }}
            </el-tag>
            <div style="margin-top: 8px">置信度: {{ (detail.confidence * 100).toFixed(1) }}%</div>
          </el-col>
          <el-col :span="12">
            <div class="detail-label">AI 关注区域</div>
            <GradCAM :src="detail.gradcam" />
          </el-col>
        </el-row>

        <el-divider />

        <div class="detail-label">详细概率</div>
        <div
          v-for="(prob, label) in detail.probabilities"
          :key="label"
          style="margin-bottom: 8px"
        >
          <div style="display: flex; justify-content: space-between">
            <span>{{ label === 'NORMAL' ? '正常' : '肺炎' }}</span>
            <span>{{ (prob * 100).toFixed(2) }}%</span>
          </div>
          <el-progress
            :percentage="prob * 100"
            :stroke-width="6"
            :color="label === 'NORMAL' ? '#67c23a' : '#f56c6c'"
          />
        </div>

        <template v-if="detail.annotation">
          <el-divider />
          <div class="detail-label">医生标注</div>
          <el-descriptions :column="1" border size="small">
            <el-descriptions-item label="是否同意">
              <el-tag v-if="detail.doctor_agreement" type="success">同意</el-tag>
              <el-tag v-else type="warning">不同意</el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="!detail.doctor_agreement && detail.correct_label" label="修正诊断">
              {{ detail.correct_label }}
            </el-descriptions-item>
            <el-descriptions-item label="标注说明">{{ detail.annotation }}</el-descriptions-item>
          </el-descriptions>
        </template>

        <div class="detail-meta">
          <span>模型: {{ detail.model_version }}</span>
          <span v-if="detail.inference_time_ms">推理耗时: {{ detail.inference_time_ms }}ms</span>
          <span>时间: {{ formatTime(detail.created_at) }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Picture, Clock, Plus } from '@element-plus/icons-vue'
import { getAnalysisHistory, getAnalysisDetail } from '@/api/imaging'
import GradCAM from '@/components/GradCAM.vue'

const list = ref([])
const loading = ref(true)
const pagination = reactive({ page: 1, size: 20, total: 0 })

const showDetail = ref(false)
const detail = ref(null)
const loadingDetail = ref(false)

const formatTime = (iso) => iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'

const load = async () => {
  loading.value = true
  try {
    const res = await getAnalysisHistory({
      limit: pagination.size,
      offset: (pagination.page - 1) * pagination.size,
    })
    list.value = res
    if (res.length < pagination.size) {
      pagination.total = (pagination.page - 1) * pagination.size + res.length
    } else {
      pagination.total = pagination.page * pagination.size + 1
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const viewDetail = async (row) => {
  showDetail.value = true
  loadingDetail.value = true
  try {
    detail.value = await getAnalysisDetail(row.id)
  } finally {
    loadingDetail.value = false
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
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
  display: flex;
}
.detail-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.detail-meta {
  margin-top: 16px;
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
  flex-wrap: wrap;
}
:deep(.el-table__row) {
  cursor: pointer;
}
</style>