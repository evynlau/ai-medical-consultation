<!-- Imaging/Analysis.vue - torchxrayvision 多分类胸片分析 -->
<template>
  <div class="imaging-analysis page-container">
    <el-card shadow="never" class="header-card">
      <template #header>
        <div class="card-header">
          <h3>
            <el-icon><Picture /></el-icon>
            AI 影像分析 - 多分类胸片病理 (xrv 官方)
          </h3>
          <div class="actions">
            <el-button @click="$router.push('/imaging/history')">
              <el-icon><Clock /></el-icon>
              历史记录
            </el-button>
          </div>
        </div>
      </template>

      <el-alert type="warning" :closable="false" class="warning-alert">
        <template #title>
          ⚠️ AI 辅助诊断工具 - 不替代专业医生诊断
        </template>
        本系统的影像分析结果仅供医生参考,不能作为最终诊断依据。最终诊断需结合临床症状、实验室检查由专业医生确认。
      </el-alert>
    </el-card>

    <!-- 上传区 -->
    <el-row :gutter="24" v-if="!result">
      <el-col :span="24">
        <el-card shadow="never">
          <template #header>
            <h4><el-icon><Upload /></el-icon> 上传胸片影像</h4>
          </template>

          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            accept="image/jpeg,image/jpg,image/png"
            :on-change="handleFileChange"
            :on-exceed="handleExceed"
            v-model:file-list="fileList"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽图片到此处,或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 JPEG/PNG 格式,文件不超过 10MB<br>
                建议上传清晰的胸部 X 光正位片
              </div>
            </template>
          </el-upload>

          <el-form v-if="fileList.length" label-width="100px" class="upload-form">
            <el-form-item label="患者ID">
              <el-input-number v-model="form.patient_id" :min="1" placeholder="可选" />
            </el-form-item>
            <el-form-item label="问诊ID">
              <el-input-number v-model="form.consultation_id" :min="1" placeholder="可选" />
            </el-form-item>
            <el-form-item label="生成热力图">
              <el-switch v-model="form.include_gradcam" active-text="Grad-CAM" />
            </el-form-item>
            <el-form-item v-if="form.include_gradcam" label="肺部分割">
              <el-switch
                v-model="form.apply_lung_mask"
                active-text="PSPNet 限制到双肺内"
                inactive-text="无限制"
              />
            </el-form-item>
            <el-form-item v-if="form.include_gradcam" label="热力图病理">
              <el-checkbox-group v-model="form.target_classes" :max="6">
                <el-checkbox
                  v-for="p in POSITIVE_PATHOLOGIES"
                  :key="p.pathology"
                  :value="p.pathology"
                  :label="p.pathology"
                >
                  {{ p.label_cn }} ({{ p.pathology }})
                </el-checkbox>
              </el-checkbox-group>
              <div class="form-hint">
                勾选要生成热力图的病理(最多 6 个,默认所有阳性)
              </div>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="analyzing"
                @click="startAnalysis"
                size="large"
              >
                <el-icon><Aim /></el-icon>
                开始 AI 分析
              </el-button>
              <el-button @click="resetUpload">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <!-- 结果区 -->
    <div v-if="result" class="result-section">
      <el-row :gutter="24">
        <!-- 左侧: 主诊断 + 影像 -->
        <el-col :xs="24" :md="12">
          <el-card shadow="never" class="image-card">
            <template #header>
              <h4>
                <el-icon><Picture /></el-icon>
                影像 - {{ result.diagnosis_cn }}
              </h4>
            </template>

            <el-row :gutter="16">
              <el-col :span="12">
                <div class="image-label">原始影像</div>
                <ImageViewer
                  :src="originalImageUrl || result.original_image"
                  alt="原始胸片"
                />
              </el-col>
              <el-col :span="12">
                <div class="image-label">{{ result.diagnosis }} 热力图</div>
                <ImageViewer
                  :src="mainGradcam?.overlay"
                  alt="热力图"
                  placeholder-text="暂无热力图"
                />
              </el-col>
            </el-row>

            <div class="image-meta">
              <el-tag size="small">文件名:{{ result.image_filename || 'N/A' }}</el-tag>
              <el-tag size="small" type="info">{{ result.model_weights }}</el-tag>
              <el-tag size="small" type="success">
                推理耗时: {{ result.inference_time_ms }}ms
              </el-tag>
              <el-tag
                v-if="result.lung_mask_applied"
                size="small"
                type="warning"
              >
                PSPNet 肺部分割
              </el-tag>
              <el-tag v-if="result.calibrated" size="small" type="success">
                已校准
              </el-tag>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧: 11 维多分类结果 -->
        <el-col :xs="24" :md="12">
          <el-card shadow="never" class="result-card">
            <template #header>
              <h4>
                <el-icon><DataAnalysis /></el-icon>
                多分类结果
                <el-tag size="small" type="danger" style="margin-left: 8px">
                  {{ result.positive_count }} / 11 阳性
                </el-tag>
              </h4>
            </template>

            <!-- 主诊断 -->
            <div class="diagnosis-box">
              <div class="diagnosis-icon">
                <el-icon :class="result.diagnosis === 'NORMAL' ? 'normal' : 'abnormal'">
                  <CircleCheck v-if="result.diagnosis === 'NORMAL'" />
                  <Warning v-else />
                </el-icon>
              </div>
              <div class="diagnosis-text">
                <div class="diagnosis-label">{{ result.diagnosis_cn }}</div>
                <div class="diagnosis-en">{{ result.diagnosis }}</div>
              </div>
              <div class="diagnosis-confidence">
                置信度 {{ (result.confidence * 100).toFixed(1) }}%
              </div>
            </div>

            <!-- 11 病理概率表 -->
            <div class="pathology-list">
              <h5>11 维病理 (torchxrayvision CheXpert)</h5>
              <div
                v-for="p in result.pathologies"
                :key="p.pathology"
                class="pathology-item"
                :class="{ positive: p.positive }"
              >
                <div class="pathology-item-header">
                  <span class="pathology-cn">{{ p.label_cn }}</span>
                  <span class="pathology-en">{{ p.pathology }}</span>
                  <el-tag
                    :type="p.positive ? 'danger' : 'success'"
                    size="small"
                    effect="dark"
                  >
                    {{ p.positive ? '阳性' : '阴性' }}
                  </el-tag>
                </div>
                <div class="pathology-item-bar">
                  <el-progress
                    :percentage="(p.probability * 100)"
                    :stroke-width="10"
                    :color="p.positive ? '#f56c6c' : '#67c23a'"
                    :format="() => `${(p.probability * 100).toFixed(1)}%`"
                  />
                </div>
                <div class="pathology-item-meta">
                  阈值 {{ (p.threshold * 100).toFixed(1) }}%
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 多热力图 (按 xrv 范式: 每个勾选病理一张) -->
      <el-card
        v-if="result.gradcams && result.gradcams.length"
        shadow="never"
        class="gradcams-card"
        style="margin-top: 24px"
      >
        <template #header>
          <h4>
            <el-icon><Aim /></el-icon>
            Grad-CAM 热力图 ({{ result.gradcams.length }} 张,HiResCAM)
          </h4>
        </template>

        <el-row :gutter="16">
          <el-col
            v-for="g in result.gradcams"
            :key="g.pathology"
            :xs="24" :sm="12" :md="8"
          >
            <div class="gradcam-item">
              <div class="gradcam-header">
                <div>
                  <span class="gradcam-cn">{{ g.label_cn }}</span>
                  <span class="gradcam-en">{{ g.pathology }}</span>
                </div>
                <el-tag :type="g.positive ? 'danger' : 'success'" size="small">
                  {{ (g.probability * 100).toFixed(1) }}%
                </el-tag>
              </div>
              <ImageViewer
                :src="originalImageUrl || result.original_image"
                :overlay-src="g.raw"
                :overlay-opacity="0.5"
                :alt="`${g.label_cn} 热力图`"
              />
              <div class="gradcam-meta">
                <span>阈值 {{ (g.threshold * 100).toFixed(0) }}%</span>
                <span :class="g.positive ? 'pos' : 'neg'">
                  {{ g.positive ? '阳性' : '阴性' }}
                </span>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>

      <!-- 医生标注 -->
      <el-card shadow="never" class="annotation-card" style="margin-top: 24px">
        <template #header>
          <h4>
            <el-icon><EditPen /></el-icon>
            医生标注
            <el-tag v-if="!result.annotation" size="small" type="info" style="margin-left: 8px">待标注</el-tag>
            <el-tag v-else size="small" type="success" style="margin-left: 8px">已标注</el-tag>
          </h4>
        </template>

        <el-form label-width="120px" :model="annotationForm" :disabled="!!result.annotation">
          <el-form-item label="是否同意 AI">
            <el-radio-group v-model="annotationForm.agreement">
              <el-radio :value="true"><el-icon><CircleCheck /></el-icon> 同意</el-radio>
              <el-radio :value="false"><el-icon><CircleClose /></el-icon> 不同意</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="annotationForm.agreement === false" label="修正诊断">
            <el-select v-model="annotationForm.correct_label" placeholder="选择正确病理">
              <el-option
                v-for="p in result.pathologies"
                :key="p.pathology"
                :value="p.pathology"
                :label="`${p.label_cn} (${p.pathology})`"
              />
              <el-option value="NORMAL" label="正常 (NORMAL)" />
            </el-select>
          </el-form-item>
          <el-form-item label="标注说明">
            <el-input
              v-model="annotationForm.annotation"
              type="textarea"
              :rows="4"
              placeholder="请输入您的专业判断..."
              maxlength="2000"
              show-word-limit
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              :loading="submitting"
              @click="submitAnnotation"
              :disabled="!annotationForm.annotation.trim() || annotationForm.agreement === null"
            >
              <el-icon><Check /></el-icon>
              提交标注
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 操作 -->
      <div class="action-bar">
        <el-button @click="resetAll">
          <el-icon><Refresh /></el-icon>
          分析新影像
        </el-button>
        <el-button type="primary" @click="$router.push('/imaging/history')">
          <el-icon><Clock /></el-icon>
          查看历史
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Picture, Clock, Upload, Aim, DataAnalysis, EditPen,
  CircleCheck, CircleClose, Warning, Check, Refresh,
} from '@element-plus/icons-vue'
import { analyzePneumonia, submitAnnotation as submitAnnotationApi } from '@/api/imaging'
import ImageViewer from '@/components/ImageViewer.vue'

const fileList = ref([])
const originalImageUrl = ref('')
const analyzing = ref(false)
const submitting = ref(false)
const result = ref(null)

const form = reactive({
  patient_id: null,
  consultation_id: null,
  include_gradcam: true,
  apply_lung_mask: true,  // 默认 PSPNet 限制
  target_classes: [],  // 空=后端自动选阳性
})

const annotationForm = reactive({
  agreement: null,
  correct_label: null,
  annotation: '',
})

// xrv 官方 11 维病理 (CheX 权重)
const POSITIVE_PATHOLOGIES = [
  { pathology: 'Atelectasis', label_cn: '肺不张' },
  { pathology: 'Consolidation', label_cn: '实变' },
  { pathology: 'Pneumothorax', label_cn: '气胸' },
  { pathology: 'Edema', label_cn: '肺水肿' },
  { pathology: 'Effusion', label_cn: '胸腔积液' },
  { pathology: 'Pneumonia', label_cn: '肺炎' },
  { pathology: 'Cardiomegaly', label_cn: '心影增大' },
  { pathology: 'Lung Lesion', label_cn: '肺内病变' },
  { pathology: 'Fracture', label_cn: '骨折' },
  { pathology: 'Lung Opacity', label_cn: '肺浑浊' },
  { pathology: 'Enlarged Cardiomediastinum', label_cn: '纵隔增宽' },
]

// 当前主诊断的热力图
const mainGradcam = computed(() => {
  if (!result.value?.gradcams) return null
  return result.value.gradcams.find(g => g.pathology === result.value.diagnosis)
    || result.value.gradcams[0]
})

const handleFileChange = (file) => {
  if (file.raw) {
    originalImageUrl.value = URL.createObjectURL(file.raw)
  }
}
const handleExceed = () => ElMessage.warning('只能上传一张图片')

const startAnalysis = async () => {
  if (!fileList.value.length) {
    ElMessage.warning('请先选择影像文件')
    return
  }
  analyzing.value = true
  try {
    const formData = new FormData()
    formData.append('file', fileList.value[0].raw)
    if (form.patient_id) formData.append('patient_id', form.patient_id)
    if (form.consultation_id) formData.append('consultation_id', form.consultation_id)
    formData.append('include_gradcam', form.include_gradcam)
    if (form.include_gradcam) {
      formData.append('apply_lung_mask', form.apply_lung_mask)
      if (form.target_classes.length) {
        formData.append('target_classes', form.target_classes.join(','))
      }
    }
    const data = await analyzePneumonia(formData)
    result.value = data
    ElMessage.success('分析完成')
  } catch (e) {
    ElMessage.error('分析失败: ' + (e.message || '未知错误'))
  } finally {
    analyzing.value = false
  }
}

const submitAnnotation = async () => {
  if (!result.value?.id) return
  submitting.value = true
  try {
    await submitAnnotationApi(result.value.id, {
      annotation: annotationForm.annotation,
      agreement: annotationForm.agreement,
      correct_label: annotationForm.correct_label,
    })
    result.value.annotation = annotationForm.annotation
    result.value.doctor_agreement = annotationForm.agreement
    result.value.correct_label = annotationForm.correct_label
    ElMessage.success('标注已保存')
  } catch (e) {
    ElMessage.error('标注失败: ' + (e.message || '未知错误'))
  } finally {
    submitting.value = false
  }
}

const resetUpload = () => {
  fileList.value = []
  originalImageUrl.value = ''
}
const resetAll = () => {
  result.value = null
  annotationForm.agreement = null
  annotationForm.correct_label = null
  annotationForm.annotation = ''
  resetUpload()
}
</script>

<style lang="scss" scoped>
.imaging-analysis {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-card h3 {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.warning-alert {
  margin-top: 8px;
}

.upload-form {
  margin-top: 16px;
}

.form-hint {
  margin-left: 12px;
  color: #909399;
  font-size: 12px;
}

.diagnosis-box {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #f0f9ff, #e0f2fe);
  border-radius: 8px;
  margin-bottom: 16px;
}

.diagnosis-icon {
  font-size: 48px;
  .normal { color: #67c23a; }
  .abnormal { color: #f56c6c; }
}

.diagnosis-text {
  flex: 1;
}
.diagnosis-label {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
.diagnosis-en {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}
.diagnosis-confidence {
  font-size: 16px;
  color: #409eff;
  font-weight: 600;
}

.pathology-list {
  h5 {
    margin: 0 0 12px 0;
    color: #303133;
    font-size: 14px;
  }
}

.pathology-item {
  padding: 8px 12px;
  border-radius: 4px;
  background: #f8f9fb;
  margin-bottom: 6px;
  border-left: 3px solid #67c23a;
  transition: all 0.2s;

  &.positive {
    background: #fef0f0;
    border-left-color: #f56c6c;
  }
}

.pathology-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.pathology-cn {
  font-weight: 600;
  color: #303133;
}

.pathology-en {
  color: #909399;
  font-size: 11px;
  flex: 1;
}

.pathology-item-bar {
  margin: 4px 0 2px 0;
}

.pathology-item-meta {
  font-size: 11px;
  color: #909399;
}

.gradcam-item {
  margin-bottom: 16px;
  padding: 12px;
  background: #fafbfc;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.gradcam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.gradcam-cn {
  font-weight: 600;
  color: #303133;
}
.gradcam-en {
  margin-left: 6px;
  color: #909399;
  font-size: 11px;
}

.gradcam-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 11px;

  .pos { color: #f56c6c; font-weight: 600; }
  .neg { color: #67c23a; }
}

.image-label {
  font-size: 12px;
  color: #606266;
  margin-bottom: 4px;
  text-align: center;
}

.image-meta {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.action-bar {
  margin-top: 24px;
  display: flex;
  gap: 12px;
}
</style>
