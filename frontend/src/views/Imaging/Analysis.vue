<!-- Imaging/Analysis.vue - 影像分析主页面 -->
<template>
  <div class="imaging-analysis page-container">
    <el-card shadow="never" class="header-card">
      <template #header>
        <div class="card-header">
          <h3>
            <el-icon><Picture /></el-icon>
            AI 影像分析 - 肺炎辅助诊断
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
        本系统的影像分析结果仅供医生参考，不能作为最终诊断依据。最终诊断需结合临床症状、实验室检查由专业医生确认。
      </el-alert>
    </el-card>

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
              拖拽图片到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                支持 JPEG/PNG 格式，文件不超过 10MB
                <br>
                建议上传清晰的胸部 X 光正位片
              </div>
            </template>
          </el-upload>

          <el-form v-if="fileList.length" label-width="100px" class="upload-form">
            <el-form-item label="患者ID">
              <el-input-number v-model="form.patient_id" :min="1" placeholder="可选" />
              <span class="form-hint">关联患者档案</span>
            </el-form-item>
            <el-form-item label="问诊ID">
              <el-input-number v-model="form.consultation_id" :min="1" placeholder="可选" />
              <span class="form-hint">关联问诊记录</span>
            </el-form-item>
            <el-form-item label="Grad-CAM">
              <el-switch v-model="form.include_gradcam" active-text="生成 AI 关注区域" />
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

    <!-- 分析结果展示 -->
    <div v-if="result" class="result-section">
      <el-row :gutter="24">
        <!-- 左侧: 原图 + AI 关注 -->
        <el-col :xs="24" :md="12">
          <el-card shadow="never" class="image-card">
            <template #header>
              <h4><el-icon><Picture /></el-icon> 影像对比</h4>
            </template>

            <el-row :gutter="16">
              <el-col :span="12">
                <div class="image-label">原始影像</div>
                <div class="image-wrapper">
                  <img
                    :src="originalImageUrl"
                    alt="原始胸片"
                    class="preview-image"
                  />
                </div>
              </el-col>
              <el-col :span="12">
                <div class="image-label">AI 关注区域</div>
                <GradCAM :src="result.gradcam" />
              </el-col>
            </el-row>

            <div class="image-meta">
              <el-tag size="small">文件名:{{ result.image_filename || 'N/A' }}</el-tag>
              <el-tag size="small" type="info">
                模型: {{ result.model_version }}
              </el-tag>
              <el-tag size="small" type="success">
                推理耗时: {{ result.inference_time_ms }}ms
              </el-tag>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧: 分析结果 -->
        <el-col :xs="24" :md="12">
          <el-card shadow="never" class="result-card">
            <template #header>
              <h4><el-icon><DataAnalysis /></el-icon> 分析结果</h4>
            </template>

            <!-- 预测结果 -->
            <div class="prediction-box" :class="predictionClass">
              <div class="prediction-icon">
                <el-icon v-if="result.prediction === 'NORMAL'"><CircleCheck /></el-icon>
                <el-icon v-else><Warning /></el-icon>
              </div>
              <div class="prediction-text">
                <div class="prediction-label">{{ result.prediction_label }}</div>
                <div class="prediction-confidence">
                  置信度: {{ (result.confidence * 100).toFixed(1) }}%
                </div>
              </div>
            </div>

            <!-- 置信度进度条 -->
            <div class="confidence-bar">
              <el-progress
                :percentage="(result.confidence * 100)"
                :stroke-width="20"
                :color="confidenceColor"
                :show-text="false"
              />
            </div>

            <!-- 详细概率 -->
            <div class="probabilities">
              <h5>详细概率</h5>
              <div
                v-for="(prob, label) in result.probabilities"
                :key="label"
                class="prob-item"
              >
                <div class="prob-label">
                  <span>{{ label === 'NORMAL' ? '正常' : '肺炎' }}</span>
                  <span class="prob-value">{{ (prob * 100).toFixed(1) }}%</span>
                </div>
                <el-progress
                  :percentage="(prob * 100)"
                  :stroke-width="8"
                  :color="label === 'NORMAL' ? '#67c23a' : '#f56c6c'"
                />
              </div>
            </div>

            <!-- 关注区域说明 -->
            <div v-if="attentionHint" class="attention-hint">
              <el-icon><Aim /></el-icon>
              <span>{{ attentionHint }}</span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 医生标注 -->
      <el-card shadow="never" class="annotation-card">
        <template #header>
          <h4>
            <el-icon><EditPen /></el-icon>
            医生标注
            <el-tag size="small" type="info" style="margin-left: 8px">
              {{ result.annotation ? '已标注' : '待标注' }}
            </el-tag>
          </h4>
        </template>

        <el-form label-width="120px" :model="annotationForm" :disabled="!!result.annotation">
          <el-form-item label="是否同意 AI 判断">
            <el-radio-group v-model="annotationForm.agreement">
              <el-radio :value="true">
                <el-icon><CircleCheck /></el-icon> 同意
              </el-radio>
              <el-radio :value="false">
                <el-icon><CircleClose /></el-icon> 不同意
              </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item v-if="!annotationForm.agreement" label="修正诊断">
            <el-radio-group v-model="annotationForm.correct_label">
              <el-radio value="NORMAL">正常</el-radio>
              <el-radio value="PNEUMONIA">肺炎</el-radio>
              <el-radio value="OTHER">其他 (需说明)</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="标注说明">
            <el-input
              v-model="annotationForm.annotation"
              type="textarea"
              :rows="4"
              placeholder="请输入您的专业判断,如:右肺下叶斑片状阴影,符合肺炎表现..."
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

      <!-- 操作按钮 -->
      <div class="action-bar">
        <el-button @click="resetAll">
          <el-icon><Refresh /></el-icon>
          分析新影像
        </el-button>
        <el-button type="primary" @click="$router.push('/imaging/history')">
          <el-icon><Clock /></el-icon>
          查看历史记录
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
import GradCAM from '@/components/GradCAM.vue'

const fileList = ref([])
const originalImageUrl = ref('')
const analyzing = ref(false)
const submitting = ref(false)
const result = ref(null)

const form = reactive({
  patient_id: null,
  consultation_id: null,
  include_gradcam: true,
})

const annotationForm = reactive({
  agreement: null,
  correct_label: null,
  annotation: '',
})

const predictionClass = computed(() => {
  if (!result.value) return ''
  return result.value.prediction === 'NORMAL' ? 'normal' : 'pneumonia'
})

const confidenceColor = computed(() => {
  if (!result.value) return '#409eff'
  if (result.value.prediction === 'NORMAL') return '#67c23a'
  return '#f56c6c'
})

const attentionHint = computed(() => {
  if (!result.value) return ''
  if (result.value.prediction === 'PNEUMONIA') {
    return 'AI 重点关注肺部纹理异常区域,请医生重点查看该区域'
  }
  return 'AI 未检测到明显异常区域,模型关注心脏及正常解剖结构'
})

const handleFileChange = (file) => {
  if (file.raw) {
    originalImageUrl.value = URL.createObjectURL(file.raw)
  }
}

const handleExceed = () => {
  ElMessage.warning('只能上传一张图片')
}

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
  if (!result.value) return

  submitting.value = true
  try {
    await submitAnnotationApi(result.value.id, {
      annotation: annotationForm.annotation,
      agreement: annotationForm.agreement,
      correct_label: !annotationForm.agreement ? annotationForm.correct_label : null,
    })
    // 更新本地结果
    result.value.annotation = annotationForm.annotation
    result.value.doctor_agreement = annotationForm.agreement
    result.value.correct_label = annotationForm.correct_label
    ElMessage.success('标注已保存')
  } catch (e) {
    ElMessage.error('提交标注失败')
  } finally {
    submitting.value = false
  }
}

const resetUpload = () => {
  fileList.value = []
  originalImageUrl.value = ''
}

const resetAll = () => {
  resetUpload()
  result.value = null
  Object.assign(form, {
    patient_id: null,
    consultation_id: null,
    include_gradcam: true,
  })
  Object.assign(annotationForm, {
    agreement: null,
    correct_label: null,
    annotation: '',
  })
}
</script>

<style lang="scss" scoped>
.imaging-analysis {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
    .actions { display: flex; gap: 8px; }
  }
}

.warning-alert {
  margin-bottom: 0;
}

.upload-form {
  margin-top: 24px;
  max-width: 600px;

  .form-hint {
    margin-left: 12px;
    color: #909399;
    font-size: 12px;
  }
}

.result-section {
  margin-top: 24px;
}

.image-card {
  height: 100%;

  .image-label {
    font-size: 13px;
    color: #606266;
    margin-bottom: 8px;
    text-align: center;
    font-weight: 500;
  }

  .image-wrapper {
    aspect-ratio: 1;
    background: #f5f7fa;
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .preview-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .image-meta {
    margin-top: 12px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
  }
}

.result-card {
  height: 100%;

  .prediction-box {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px;
    border-radius: 8px;
    margin-bottom: 16px;

    &.normal {
      background: linear-gradient(135deg, #f0f9ff 0%, #d4f1e2 100%);
      border-left: 4px solid #67c23a;
    }

    &.pneumonia {
      background: linear-gradient(135deg, #fef0f0 0%, #fde2e2 100%);
      border-left: 4px solid #f56c6c;
    }
  }

  .prediction-icon {
    font-size: 48px;

    .normal & { color: #67c23a; }
    .pneumonia & { color: #f56c6c; }
  }

  .prediction-label {
    font-size: 24px;
    font-weight: 600;
    color: #303133;
  }

  .prediction-confidence {
    font-size: 14px;
    color: #606266;
    margin-top: 4px;
  }

  .confidence-bar {
    margin-bottom: 24px;
  }

  .probabilities {
    h5 {
      margin: 0 0 12px;
      color: #303133;
      font-size: 14px;
    }
  }

  .prob-item {
    margin-bottom: 12px;
  }

  .prob-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 4px;
    font-size: 13px;
    color: #606266;
  }

  .prob-value {
    font-weight: 500;
    color: #303133;
  }

  .attention-hint {
    margin-top: 16px;
    padding: 12px;
    background: #f0f9ff;
    border-radius: 6px;
    color: #1976d2;
    font-size: 13px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
}

.annotation-card {
  margin-top: 24px;
  h4 { margin: 0; display: flex; align-items: center; gap: 6px; }
}

.action-bar {
  margin-top: 24px;
  display: flex;
  justify-content: center;
  gap: 12px;
}
</style>