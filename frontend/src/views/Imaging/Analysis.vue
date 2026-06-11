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
            <el-form-item v-if="form.include_gradcam" label="算法选择">
              <el-radio-group v-model="form.gradcam_method">
                <el-radio-button value="hirescam">HiResCAM (推荐)</el-radio-button>
                <el-radio-button value="gradcam">Grad-CAM</el-radio-button>
              </el-radio-group>
              <span class="form-hint">
                HiResCAM 空间分辨率更高，边界更清晰
              </span>
            </el-form-item>
            <el-form-item v-if="form.include_gradcam" label="高亮病理">
              <el-checkbox-group v-model="form.target_classes" :max="6">
                <el-checkbox
                  v-for="p in PATHOLOGIES"
                  :key="p.en"
                  :value="p.en"
                  :label="p.en"
                >
                  {{ p.cn }}
                  <span class="pathology-en">{{ p.en }}</span>
                </el-checkbox>
              </el-checkbox-group>
              <div class="form-hint">
                勾选要同时生成热力图的病理(最多 6 个),每张热力图都限制在双肺内
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
                <ImageViewer
                  :src="originalImageUrl"
                  :overlay-src="result.gradcam_raw && viewMode === 'overlay' ? result.gradcam_raw : ''"
                  :overlay-opacity="overlayOpacity"
                  alt="原始胸片"
                  placeholder-text="请上传影像"
                />
              </el-col>
              <el-col :span="12">
                <div class="image-label">AI 关注区域</div>
                <ImageViewer
                  :src="result.gradcam"
                  alt="热力图"
                  placeholder-text="暂无热力图"
                />
              </el-col>
            </el-row>

            <div class="view-mode-bar">
              <el-radio-group v-model="viewMode" size="small">
                <el-radio-button label="side-by-side">并排对比</el-radio-button>
                <el-radio-button label="overlay">叠加显示</el-radio-button>
                <el-radio-button label="separate">分别显示</el-radio-button>
              </el-radio-group>
              <div v-if="viewMode === 'overlay'" class="opacity-control">
                <span>热力图透明度</span>
                <el-slider
                  v-model="overlayOpacity"
                  :min="10"
                  :max="100"
                  :step="5"
                  style="width: 120px; margin: 0 12px;"
                />
                <span>{{ overlayOpacity }}%</span>
              </div>
              <el-button size="small" @click="openFullscreen">
                <el-icon><FullScreen /></el-icon>
                全屏对比
              </el-button>
            </div>

            <div class="image-meta">
              <el-tag size="small">文件名:{{ result.image_filename || 'N/A' }}</el-tag>
              <el-tag size="small" type="info">
                模型: {{ result.model_version }}
              </el-tag>
              <el-tag size="small" type="success">
                推理耗时: {{ result.inference_time_ms }}ms
              </el-tag>
              <el-tag
                v-if="result.lung_mask_applied"
                size="small"
                type="warning"
              >
                已应用 PSPNet 肺部分割
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

            <!-- 11 维多标签报告 (CheXpert 权重) -->
            <div v-if="result.multi_pathology_scores || result.all_pathology_scores" class="multi-report">
              <h5>
                多标签报告 (CheXpert 11 类)
                <el-tag size="small" type="info" style="margin-left: 6px">torchxrayvision</el-tag>
              </h5>
              <div class="pathology-grid">
                <div
                  v-for="(info, key) in (result.multi_pathology_scores || result.all_pathology_scores)"
                  :key="key"
                  class="pathology-cell"
                  :class="{ positive: info.positive, selected: form.target_classes.includes(key) }"
                >
                  <div class="pathology-cell-name">
                    {{ info.label_cn || key }}
                    <span class="pathology-cell-en">{{ key }}</span>
                  </div>
                  <div class="pathology-cell-bar">
                    <el-progress
                      :percentage="(info.probability * 100)"
                      :stroke-width="6"
                      :show-text="false"
                      :color="info.positive ? '#f56c6c' : '#67c23a'"
                    />
                  </div>
                  <div class="pathology-cell-meta">
                    <span :class="info.positive ? 'pos' : 'neg'">
                      {{ (info.probability * 100).toFixed(1) }}%
                    </span>
                    <span class="thresh">阈值 {{ (info.threshold * 100).toFixed(0) }}%</span>
                  </div>
                </div>
              </div>
              <div v-if="result.top_findings && result.top_findings.length" class="top-findings">
                <el-icon><Aim /></el-icon>
                <span>Top 发现: </span>
                <el-tag
                  v-for="f in result.top_findings"
                  :key="f"
                  size="small"
                  type="danger"
                  effect="dark"
                  style="margin-left: 4px"
                >
                  {{ PATHOLOGY_LABELS_CN_MAP[f] || f }}
                </el-tag>
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

      <!-- 多热力图展示: 每个勾选病理一张 -->
      <el-card
        v-if="result.gradcams && result.gradcams.length > 1"
        shadow="never"
        class="multi-gradcam-card"
        style="margin-top: 24px"
      >
        <template #header>
          <div class="card-header">
            <h4>
              <el-icon><Aim /></el-icon>
              多病理 AI 关注区域 ({{ result.gradcams.length }} 张热力图)
            </h4>
            <el-button size="small" @click="openMultiFullscreen">
              <el-icon><FullScreen /></el-icon>
              全屏对比
            </el-button>
          </div>
        </template>

        <el-row :gutter="16">
          <el-col
            v-for="(g, idx) in result.gradcams"
            :key="g.pathology"
            :xs="24" :sm="12" :md="8"
          >
            <div class="multi-gradcam-item">
              <div class="multi-gradcam-header">
                <div>
                  <span class="multi-gradcam-cn">{{ g.label_cn }}</span>
                  <span class="multi-gradcam-en">{{ g.pathology }}</span>
                </div>
                <el-tag
                  :type="g.positive ? 'danger' : 'success'"
                  size="small"
                >
                  {{ (g.probability * 100).toFixed(1) }}%
                </el-tag>
              </div>
              <ImageViewer
                :src="originalImageUrl || result.original_image"
                :overlay-src="g.gradcam_raw"
                :overlay-opacity="0.5"
                :alt="`${g.label_cn} 热力图`"
                placeholder-text="无"
              />
              <div class="multi-gradcam-meta">
                <span class="thresh-text">阈值 {{ (g.threshold * 100).toFixed(0) }}%</span>
                <span :class="g.positive ? 'pos' : 'neg'">
                  {{ g.positive ? '阳性' : '阴性' }}
                </span>
              </div>
            </div>
          </el-col>
        </el-row>
      </el-card>

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

    <!-- 全屏对比对话框 -->
    <el-dialog
      v-model="showFullscreen"
      title="影像全屏对比"
      width="95%"
      top="2vh"
      :show-close="true"
      destroy-on-close
    >
      <div v-if="result" class="fullscreen-container">
        <div class="fullscreen-toolbar">
          <el-radio-group v-model="viewMode" size="default">
            <el-radio-button label="side-by-side">并排对比</el-radio-button>
            <el-radio-button label="overlay">叠加显示</el-radio-button>
            <el-radio-button label="separate">分别显示</el-radio-button>
          </el-radio-group>
          <div v-if="viewMode === 'overlay'" class="opacity-control">
            <span>热力图透明度</span>
            <el-slider
              v-model="overlayOpacity"
              :min="10"
              :max="100"
              :step="5"
              style="width: 160px; margin: 0 12px;"
            />
            <span>{{ overlayOpacity }}%</span>
          </div>
        </div>

        <div
          v-if="viewMode === 'side-by-side'"
          class="fullscreen-images"
        >
          <div class="fullscreen-image-pane">
            <h4>原始影像</h4>
            <ImageViewer
              :src="originalImageUrl || result.original_image"
              alt="原始胸片"
            />
          </div>
          <div class="fullscreen-image-pane">
            <h4>AI 关注区域 (热力图)</h4>
            <ImageViewer
              :src="result.gradcam"
              alt="热力图"
            />
          </div>
        </div>

        <div
          v-else-if="viewMode === 'overlay'"
          class="fullscreen-overlay"
        >
          <h4>原图 + AI 关注区域叠加</h4>
          <ImageViewer
            :src="originalImageUrl || result.original_image"
            :overlay-src="result.gradcam_raw"
            :overlay-opacity="overlayOpacity / 100"
            alt="叠加对比"
          />
          <div class="overlay-legend">
            <span class="legend-label">低关注</span>
            <div class="legend-gradient"></div>
            <span class="legend-label">高关注</span>
          </div>
        </div>

        <div
          v-else
          class="fullscreen-images"
        >
          <div class="fullscreen-image-pane">
            <h4>原始影像</h4>
            <ImageViewer
              :src="originalImageUrl || result.original_image"
              alt="原始胸片"
            />
          </div>
          <div class="fullscreen-image-pane">
            <h4>AI 关注区域</h4>
            <ImageViewer
              :src="result.gradcam_raw"
              alt="热力图(原始)"
            />
          </div>
          <div class="fullscreen-image-pane">
            <h4>已叠加(原图+热度)</h4>
            <ImageViewer
              :src="result.gradcam"
              alt="叠加图"
            />
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Picture, Clock, Upload, Aim, DataAnalysis, EditPen,
  CircleCheck, CircleClose, Warning, Check, Refresh,
  FullScreen,
} from '@element-plus/icons-vue'
import { analyzePneumonia, submitAnnotation as submitAnnotationApi } from '@/api/imaging'
import ImageViewer from '@/components/ImageViewer.vue'

const fileList = ref([])
const originalImageUrl = ref('')
const analyzing = ref(false)
const submitting = ref(false)
const result = ref(null)

// 显示模式: side-by-side(并排) | overlay(叠加) | separate(分别)
const viewMode = ref('side-by-side')
const overlayOpacity = ref(50)

const form = reactive({
  patient_id: null,
  consultation_id: null,
  include_gradcam: true,
  gradcam_method: 'hirescam',
  // 多选病理热力图 (默认勾选 3 个 CheX 模型区分度最好的)
  // Pneumonia 走 RSNA 主诊断模型, 这里只用于生成热力图可视化
  // Effusion / Cardiomegaly / Pneumothorax 是 CheX 上区分度最强的三类
  target_classes: ['Pneumonia', 'Effusion', 'Cardiomegaly'],
})

// 11 类病理有效列表 (torchxrayvision CheXpert 权重, 其他权重 7 个类别是空)
// 比 all-model 的 18 类区分度更好 (82% vs 62% on chest_xray)
const PATHOLOGIES = [
  { en: 'Atelectasis', cn: '肺不张' },
  { en: 'Consolidation', cn: '实变' },
  { en: 'Pneumothorax', cn: '气胸' },
  { en: 'Edema', cn: '肺水肿' },
  { en: 'Effusion', cn: '胸腔积液' },
  { en: 'Pneumonia', cn: '肺炎' },
  { en: 'Cardiomegaly', cn: '心影增大' },
  { en: 'Lung Lesion', cn: '肺内病变' },
  { en: 'Fracture', cn: '骨折' },
  { en: 'Lung Opacity', cn: '肺浑浊' },
  { en: 'Enlarged Cardiomediastinum', cn: '纵隔增宽' },
]

// 病理英文 -> 中文 映射(供 top_findings 等场景)
const PATHOLOGY_LABELS_CN_MAP = PATHOLOGIES.reduce((acc, p) => {
  acc[p.en] = p.cn
  return acc
}, {})

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
    if (form.include_gradcam) {
      formData.append('gradcam_method', form.gradcam_method)
      if (form.target_classes && form.target_classes.length) {
        formData.append('target_classes', form.target_classes.join(','))
      } else {
        formData.append('target_classes', 'Pneumonia')
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

// 全屏对比模式
const showFullscreen = ref(false)
const openFullscreen = () => {
  if (!result.value) {
    ElMessage.warning('请先上传影像')
    return
  }
  showFullscreen.value = true
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

// ==================== 显示模式样式 ====================
.image-card :deep(.el-row) {
  .image-label {
    margin-bottom: 8px;
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

// ==================== 影像显示模式栏 ====================
.view-mode-bar {
  margin-top: 12px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;

  .opacity-control {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: #606266;
  }
}

// ==================== 全屏对比样式 ====================
.fullscreen-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 80vh;
}

.fullscreen-toolbar {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  flex-shrink: 0;

  .opacity-control {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: #606266;
  }
}

.fullscreen-images {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(0, 1fr));
  gap: 16px;
  min-height: 0;
}

.fullscreen-image-pane {
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  border-radius: 8px;
  overflow: hidden;
  min-height: 0;

  h4 {
    margin: 0;
    padding: 12px 16px;
    background: #fff;
    border-bottom: 1px solid #ebeef5;
    font-size: 14px;
    color: #303133;
    text-align: center;
    flex-shrink: 0;
  }
}

.fullscreen-overlay {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fafbfc;
  border-radius: 8px;
  overflow: hidden;
  min-height: 0;

  h4 {
    margin: 0;
    padding: 12px 16px;
    background: #fff;
    border-bottom: 1px solid #ebeef5;
    font-size: 14px;
    color: #303133;
    text-align: center;
    flex-shrink: 0;
  }

  .overlay-legend {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding: 12px;
    background: #fff;
    border-top: 1px solid #ebeef5;
    font-size: 13px;
    color: #606266;
    flex-shrink: 0;

    .legend-label {
      color: #606266;
    }

    .legend-gradient {
      width: 200px;
      height: 12px;
      border-radius: 6px;
      background: linear-gradient(
        to right,
        rgb(0, 0, 255),
        rgb(0, 255, 255),
        rgb(0, 255, 0),
        rgb(255, 255, 0),
        rgb(255, 0, 0)
      );
    }
  }
}

/* 多选病理复选框网格 */
:deep(.el-checkbox-group) {
  display: grid !important;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px 16px;

  .el-checkbox {
    margin-right: 0 !important;
    margin-left: 0 !important;
    .pathology-en {
      margin-left: 4px;
      color: #909399;
      font-size: 11px;
    }
  }
}

/* 11 维多标签报告 (CheXpert) */
.multi-report {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;

  h5 {
    margin: 0 0 12px 0;
    font-size: 14px;
    color: #303133;
  }
}

.pathology-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 6px 10px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}

.pathology-cell {
  padding: 6px 10px;
  border-radius: 4px;
  background: #f8f9fb;
  border: 1px solid transparent;
  transition: all 0.2s;
  font-size: 12px;

  &.positive {
    background: #fef0f0;
    border-color: #fbc4c4;
  }

  &.selected {
    border-color: #409eff;
    box-shadow: 0 0 0 1px #409eff inset;
  }
}

.pathology-cell-name {
  display: flex;
  justify-content: space-between;
  font-weight: 500;
  color: #303133;

  .pathology-cell-en {
    color: #909399;
    font-size: 10px;
    font-weight: 400;
  }
}

.pathology-cell-bar {
  margin: 4px 0;
}

.pathology-cell-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;

  .pos { color: #f56c6c; font-weight: 600; }
  .neg { color: #67c23a; }
  .thresh { color: #909399; }
}

.top-findings {
  margin-top: 10px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  font-size: 13px;
  color: #606266;
}

/* 多热力图网格 */
.multi-gradcam-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.multi-gradcam-item {
  margin-bottom: 16px;
  padding: 12px;
  background: #fafbfc;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.multi-gradcam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
}

.multi-gradcam-cn {
  font-weight: 600;
  color: #303133;
}

.multi-gradcam-en {
  margin-left: 6px;
  color: #909399;
  font-size: 11px;
}

.multi-gradcam-meta {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 11px;

  .thresh-text { color: #909399; }
  .pos { color: #f56c6c; font-weight: 600; }
  .neg { color: #67c23a; }
}

/* 复选框容器占满 */
:deep(.el-form-item__content .el-checkbox-group) {
  width: 100%;
}
</style>