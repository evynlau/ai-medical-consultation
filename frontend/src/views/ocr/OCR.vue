<template>
  <div class="ocr-page page-container">
    <PageHero
      badge="OCR 提取 · LLM 结构化 · 一键转入问诊"
      title="报告识别"
      subtitle="拍照上传处方或检验报告,自动提取文字并结构化为可机读 JSON,二次解读无忧。"
      :icon="PictureFilled"
      :variant="3"
    />

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3><el-icon><PictureFilled /></el-icon> 处方/检查报告 OCR 识别</h3>
          <el-button @click="showHistory = !showHistory">
            <el-icon><Clock /></el-icon>
            {{ showHistory ? '返回上传' : '查看历史' }}
          </el-button>
        </div>
      </template>

      <!-- 上传区 -->
      <div v-if="!showHistory" v-loading="uploading">
        <el-radio-group v-model="imageType" class="type-selector">
          <el-radio-button label="auto">自动识别</el-radio-button>
          <el-radio-button label="prescription">处方笺</el-radio-button>
          <el-radio-button label="report">检查报告</el-radio-button>
        </el-radio-group>

        <el-upload
          ref="uploadRef"
          class="upload-area"
          :auto-upload="false"
          :show-file-list="false"
          :on-change="handleFileChange"
          :accept="'image/jpeg,image/png,image/jpg,image/webp,image/bmp'"
          drag
        >
          <div v-if="!previewUrl" class="upload-placeholder">
            <el-icon :size="60" color="#909399"><UploadFilled /></el-icon>
            <div class="upload-text">点击或拖拽图片到此处</div>
            <div class="upload-hint">支持 JPG / PNG / WEBP / BMP,最大 10MB</div>
          </div>
          <div v-else class="preview-wrap">
            <img :src="previewUrl" class="preview-img" />
            <div class="preview-actions">
              <el-button @click.stop="clearFile" type="danger" plain>
                <el-icon><Delete /></el-icon>
                重新选择
              </el-button>
            </div>
          </div>
        </el-upload>

        <div v-if="selectedFile" class="action-bar">
          <el-button type="primary" size="large" :loading="uploading" @click="submitUpload">
            <el-icon><MagicStick /></el-icon>
            开始识别
          </el-button>
          <span class="file-info">
            {{ selectedFile.name }} ({{ (selectedFile.size/1024).toFixed(1) }} KB)
          </span>
        </div>

        <el-alert
          type="info"
          :closable="false"
          style="margin-top: 16px"
          show-icon
        >
          <template #title>
            💡 使用提示
          </template>
          上传处方/检验报告图片,系统会用 OCR 提取文字 + LLM 结构化。
          当前未安装 tesseract,演示模式会返回示例文本;装上 tesseract-ocr 后自动切真实识别。
        </el-alert>
      </div>

      <!-- 历史列表 -->
      <div v-else>
        <el-table :data="history" v-loading="loadingHistory" stripe>
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="row.image_type === 'prescription' ? 'warning' : 'success'" size="small">
                {{ typeLabel(row.image_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="文件名" prop="file_name" show-overflow-tooltip />
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ (row.file_size/1024).toFixed(1) }} KB</template>
          </el-table-column>
          <el-table-column label="置信度" width="120">
            <template #default="{ row }">
              <el-progress :percentage="Math.round(row.confidence * 100)" :stroke-width="8" />
            </template>
          </el-table-column>
          <el-table-column label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button size="small" type="primary" @click="viewRecord(row)">查看</el-button>
              <el-button size="small" type="danger" @click="confirmDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-model:current-page="ocrPage.page"
          v-model:page-size="ocrPage.size"
          :total="ocrPage.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          class="pagination"
          @current-change="loadHistory"
          @size-change="loadHistory"
        />
        <el-empty v-if="!loadingHistory && history.length === 0" description="还没有 OCR 记录" />
      </div>
    </el-card>

    <!-- 结果展示对话框 -->
    <el-dialog v-model="showResult" title="OCR 识别结果" width="900px" top="5vh">
      <div v-if="result" class="result-content">
        <el-row :gutter="12" class="meta-row">
          <el-col :span="6">
            <el-statistic :value="result.id" title="记录 ID" />
          </el-col>
          <el-col :span="6">
            <el-statistic :value="(result.confidence * 100).toFixed(0) + '%'" title="置信度" />
          </el-col>
          <el-col :span="6">
            <el-statistic :value="result.ocr_engine" title="OCR 引擎" />
          </el-col>
          <el-col :span="6">
            <el-statistic :value="(result.file_size/1024).toFixed(1) + ' KB'" title="文件大小" />
          </el-col>
        </el-row>

        <!-- ========== LLM 结构化结果 ========== -->
        <h4 v-if="result.structured_data?.document_type && result.structured_data.document_type !== 'unknown'">📋 结构化结果(LLM 提取)</h4>
        <div v-if="result.structured_data?.document_type === 'prescription'" class="structured">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="医院">{{ result.structured_data.hospital || '-' }}</el-descriptions-item>
            <el-descriptions-item label="科室">{{ result.structured_data.department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="患者" :span="2">
              <span v-if="result.structured_data.patient">
                {{ result.structured_data.patient.name }} /
                {{ result.structured_data.patient.gender }} /
                {{ result.structured_data.patient.age }}岁
              </span>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="医生">{{ result.structured_data.doctor || '-' }}</el-descriptions-item>
            <el-descriptions-item label="日期">{{ result.structured_data.date || '-' }}</el-descriptions-item>
            <el-descriptions-item label="诊断" :span="2">
              <el-tag v-for="d in result.structured_data.diagnosis || []" :key="d" size="small" style="margin: 2px">
                {{ d }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
          <h5>💊 用药清单</h5>
          <el-table :data="result.structured_data.medications || []" border size="small">
            <el-table-column prop="name" label="药品" min-width="140" />
            <el-table-column prop="dose" label="剂量" width="100" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="frequency" label="频次" width="100" />
            <el-table-column prop="route" label="途径" width="100" />
            <el-table-column prop="duration" label="疗程" width="80" />
          </el-table>
          <div v-if="result.structured_data.instructions" class="instructions">
            <strong>📌 医嘱:</strong>{{ result.structured_data.instructions }}
          </div>
        </div>

        <div v-else-if="result.structured_data?.document_type === 'report'" class="structured">
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="医院">{{ result.structured_data.hospital || '-' }}</el-descriptions-item>
            <el-descriptions-item label="科室">{{ result.structured_data.department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="患者" :span="2">
              <span v-if="result.structured_data.patient">
                {{ result.structured_data.patient.name }} /
                {{ result.structured_data.patient.gender }} /
                {{ result.structured_data.patient.age }}岁
              </span>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="日期" :span="2">{{ result.structured_data.date || '-' }}</el-descriptions-item>
          </el-descriptions>
          <h5>🧪 检验项目 <span class="abnormal-count" v-if="abnormalCount > 0">({{ abnormalCount }} 项异常)</span></h5>
          <el-table :data="result.structured_data.items || []" border size="small" class="test-table">
            <el-table-column type="index" width="50" />
            <el-table-column prop="name" label="项目" min-width="180" />
            <el-table-column prop="result" label="结果" width="120">
              <template #default="{ row }">
                <span :class="['result-cell', row.abnormal]">
                  {{ row.result }}
                  <span v-if="row.abnormal === 'high'" class="flag">↑</span>
                  <span v-else-if="row.abnormal === 'low'" class="flag">↓</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="unit" label="单位" width="120" />
            <el-table-column prop="reference_range" label="参考范围" min-width="160" />
          </el-table>
          <div v-if="result.structured_data.summary" class="summary">
            <strong>📝 总结:</strong>{{ result.structured_data.summary }}
          </div>
        </div>

        <div v-else-if="result.structured_data && result.structured_data.document_type === 'unknown'">
          <el-alert type="warning" :closable="false" title="未能自动识别文档类型,显示原文">
            <pre class="raw-text">{{ (result.structured_data.raw_excerpt || result.structured_data.raw_response || '').slice(0, 500) }}</pre>
          </el-alert>
        </div>

        <!-- ========== 智能解析的原文视图 ========== -->
        <h4>📄 报告原文(智能解析)</h4>
        <div class="parsed-text" v-if="parsed">
          <!-- 头部信息 -->
          <div v-if="parsed.header.length" class="parsed-section header-section">
            <div v-for="(line, i) in parsed.header" :key="'h'+i" class="header-line">{{ line }}</div>
          </div>

          <!-- 患者信息(KV 列表) -->
          <el-descriptions
            v-if="parsed.patient.length"
            class="parsed-section"
            :column="3"
            border
            size="small"
            title="📋 患者信息"
          />
          <el-descriptions
            v-if="parsed.patient.length"
            :column="3"
            border
            size="small"
            style="margin-bottom: 12px"
          >
            <el-descriptions-item v-for="(kv, i) in parsed.patient" :key="'p'+i" :label="kv.k">
              <span v-if="kv.k === '临床诊断'" class="diag-highlight">{{ kv.v }}</span>
              <span v-else>{{ kv.v }}</span>
            </el-descriptions-item>
          </el-descriptions>

          <!-- 检验项目表格 -->
          <div v-if="parsed.testRows.length" class="parsed-section">
            <h5>🔬 检验项目({{ parsed.testRows.length - 1 }} 项数据)</h5>
            <el-table :data="parsed.testRows" border size="small" class="test-table">
              <el-table-column
                v-for="(col, i) in parsed.testColumns"
                :key="'tc'+i"
                :prop="col"
                :label="col"
                min-width="100"
              >
                <template #default="{ row }">
                  <span v-if="i > 0 && (row[col]?.includes('↑') || row[col]?.includes('↓'))" class="abnormal">
                    {{ row[col] }}
                  </span>
                  <span v-else>{{ row[col] }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <!-- 备注 / 脚注 -->
          <div v-if="parsed.footer.length" class="parsed-section footer-section">
            <h5>📝 备注</h5>
            <div v-for="(line, i) in parsed.footer" :key="'f'+i" class="footer-line">{{ line }}</div>
          </div>
        </div>

        <!-- ========== 折叠的纯文本 ========== -->
        <el-collapse class="raw-collapse">
          <el-collapse-item title="📋 查看原始 OCR 文本" name="1">
            <pre class="raw-text-plain">{{ result.raw_text }}</pre>
          </el-collapse-item>
        </el-collapse>

        <!-- ========== 行动按钮 ========== -->
        <div class="action-buttons">
          <el-button type="primary" size="large" @click="startConsultFromOcr" :icon="ChatLineSquare">
            基于此报告开始问诊
          </el-button>
          <el-button size="large" @click="copyReport" :icon="DocumentCopy">
            复制结构化结果
          </el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatLineSquare, DocumentCopy, PictureFilled } from '@element-plus/icons-vue'
import { ocrApi } from '@/api/ocr'
import { useChatStore } from '@/stores/chat'
import { useRouter } from 'vue-router'
import PageHero from '@/components/PageHero.vue'

const imageType = ref('auto')
const selectedFile = ref(null)
const previewUrl = ref('')
const uploading = ref(false)
const result = ref(null)
const showResult = ref(false)
const showHistory = ref(false)
const history = ref([])
const ocrPage = reactive({ page: 1, size: 20, total: 0 })
const loadingHistory = ref(false)
const uploadRef = ref(null)
const router = useRouter()
const chatStore = useChatStore()

const typeLabel = (t) => ({ prescription: '处方', report: '报告', other: '其他', auto: '自动' }[t] || t)
const formatTime = (iso) => iso ? new Date(iso).toLocaleString('zh-CN', { hour12: false }) : '-'

/** 为 OCR 报告生成简短标题(用于 chief_complaint)
 *  - 避免顶部标题被全文报告撑爆
 *  - 最多 30 字
 */
const buildShortTitle = (patient, docType, abnormalItems) => {
  const name = patient?.name || '患者'
  const abnormalCount = (abnormalItems || []).length
  if (abnormalCount > 0) {
    return `请解读${name}的${docType}(${abnormalCount} 项异常)`
  }
  return `请解读${name}的${docType}`
}

// 异常项数量
const abnormalCount = computed(() => {
  if (!result.value?.structured_data?.items) return 0
  return result.value.structured_data.items.filter(i => i.abnormal && i.abnormal !== 'normal').length
})

// ============== 智能解析 OCR 文本 ==============
const parsed = computed(() => {
  if (!result.value?.raw_text) return null
  return parseReportText(result.value.raw_text)
})

function parseReportText(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(l => l)
  const result = { header: [], patient: [], testRows: [], testColumns: [], footer: [] }

  // 表头行:医院/机构/报告单
  const headerPatterns = [/医院/, /诊所/, /检验报告单?$/, /处方笺?$/, /门诊$/, /检测中心/, /医科大学/, /医学院/, /人民医院$/, /中医院$/, /中心医院/]
  // KV 行:键:值
  const kvPattern = /^([一-鿿]{2,6})[::]\s*(.+)$/
  // 表格行:多列(>=3 个 token),含数字或 ↑↓
  // 表格头:含"项目""结果""参考""单位""代号"
  const tableHeaderPattern = /项目|结果|参考|单位|代号|项目名称/

  let mode = 'header'  // header -> patient -> table -> footer
  let i = 0

  for (const line of lines) {
    // 表格头/数据
    if (tableHeaderPattern.test(line) && line.split(/\s+/).length >= 2) {
      // 这可能是表头
      mode = 'table'
      const cols = line.split(/\s+/).filter(c => c)
      result.testColumns = cols
      // 下一行如果像表格分隔线(---),跳过
      continue
    }

    if (mode === 'table') {
      // 检查这行是否还是表格行
      const tokens = line.split(/\s{2,}|\t/).map(t => t.trim()).filter(t => t)
      if (tokens.length >= 3) {
        result.testRows.push(parseTableRow(tokens, result.testColumns))
        continue
      } else {
        // 出表格
        mode = 'footer'
      }
    }

    // KV 行
    const kvMatch = line.match(kvPattern)
    if (kvMatch) {
      mode = 'patient'
      result.patient.push({ k: kvMatch[1], v: kvMatch[2] })
      continue
    }

    // 头部行
    if (mode === 'header' || headerPatterns.some(p => p.test(line))) {
      result.header.push(line)
      continue
    }

    // 其他都进 footer
    result.footer.push(line)
  }

  return result
}

function parseTableRow(tokens, columns) {
  const row = {}
  // 简单策略:把 token 按列数对齐
  if (tokens.length === columns.length) {
    columns.forEach((col, i) => row[col] = tokens[i] || '')
  } else if (tokens.length > columns.length) {
    // 多余的 token 合并到第一列(项目名可能含空格)
    row[columns[0]] = tokens.slice(0, tokens.length - columns.length + 1).join(' ')
    columns.slice(1).forEach((col, i) => row[col] = tokens[tokens.length - columns.length + 1 + i] || '')
  } else {
    columns.forEach((col, i) => row[col] = tokens[i] || '')
  }
  return row
}

// ============== 上传 / 历史 ==============
const handleFileChange = (file) => {
  if (!file.raw) return
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error('文件不能超过 10MB')
    return
  }
  selectedFile.value = file.raw
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = URL.createObjectURL(file.raw)
}

const clearFile = () => {
  selectedFile.value = null
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = ''
  }
}

const submitUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择图片')
    return
  }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', selectedFile.value)
    form.append('image_type', imageType.value)
    const res = await ocrApi.upload(form)
    ElMessage.success('识别完成')
    result.value = res
    showResult.value = true
  } catch (e) {
    // 错误已拦截
  } finally {
    uploading.value = false
  }
}

const loadHistory = async () => {
  loadingHistory.value = true
  try {
    const res = await ocrApi.records({
      limit: ocrPage.size,
      offset: (ocrPage.page - 1) * ocrPage.size
    })
    history.value = res
    if (res.length < ocrPage.size) {
      ocrPage.total = (ocrPage.page - 1) * ocrPage.size + res.length
    } else {
      ocrPage.total = ocrPage.page * ocrPage.size + 1
    }
  } finally {
    loadingHistory.value = false
  }
}

const viewRecord = async (row) => {
  const detail = await ocrApi.record(row.id)
  result.value = detail
  showResult.value = true
}

const confirmDelete = async (row) => {
  await ElMessageBox.confirm(`确认删除「${row.file_name}」?`, '提示', { type: 'warning' })
  await ocrApi.remove(row.id)
  ElMessage.success('已删除')
  loadHistory()
}

// ============== 基于此报告问诊 ==============
const startConsultFromOcr = async () => {
  if (!result.value) return
  const sd = result.value.structured_data || {}
  const patient = sd.patient || {}
  const diagnosis = sd.diagnosis || []
  const abnormalItems = (sd.items || []).filter(i => i.abnormal && i.abnormal !== 'normal')
  const meds = sd.medications || []
  const docType = sd.document_type === 'prescription' ? '处方' : '检验报告'

  // 构造主诉:结构化字段 + 原文 fallback
  let fullContext = `我刚做完检查,这是${docType}内容,请帮我分析。\n\n`
  if (patient.name) fullContext += `【患者】${patient.name} ${patient.gender || ''} ${patient.age || ''}岁\n`
  if (sd.hospital) fullContext += `【医院】${sd.hospital} ${sd.department || ''}\n`
  if (sd.date) fullContext += `【日期】${sd.date}\n`
  if (diagnosis.length) fullContext += `【临床诊断】${diagnosis.join('、')}\n`
  if (abnormalItems.length) {
    fullContext += `\n【异常指标】\n`
    abnormalItems.forEach(item => {
      const flag = item.abnormal === 'high' ? '↑' : '↓'
      fullContext += `  • ${item.name}: ${item.result} ${item.unit || ''} ${flag} (参考 ${item.reference_range || '-'})\n`
    })
  }
  if (sd.summary) fullContext += `\n【AI 初步总结】${sd.summary}\n`
  if (meds.length) {
    fullContext += `\n【用药】${meds.map(m => m.name).join('、')}\n`
  }

  // **关键 fallback**:如果结构化数据几乎没有,把 OCR 原文也带上
  const hasStructured = patient.name || diagnosis.length || abnormalItems.length || sd.summary
  if (!hasStructured && result.value.raw_text) {
    fullContext += `\n【报告/处方原文】\n${result.value.raw_text}\n`
  }

  fullContext += `\n请结合以上${docType},告诉我:\n1. 这些异常指标意味着什么?\n2. 需要进一步做什么检查?\n3. 日常生活需要注意什么?`

  // 长度预警
  if (fullContext.length > 9000) {
    ElMessage.warning(`报告内容较长(${fullContext.length} 字符),将以"详情"形式追加`)
  }

  // **短标题**:用于 chief_complaint,避免顶部标题被全文撑爆
  // 例如 "请解读李四的检验报告(4 项异常)"
  const shortTitle = buildShortTitle(patient, docType, abnormalItems)

  // 存到 chat store:title = 短标题(content 仍存完整内容)
  chatStore.pendingContext = {
    type: 'ocr_report',
    ocrId: result.value.id,
    summary: `${patient.name || '患者'}的${docType}`,
    title: shortTitle,
    content: fullContext,
  }

  ElMessage.success('正在跳转到问诊,报告内容已自动填入...')
  showResult.value = false
  router.push('/chat')
}

const copyReport = async () => {
  if (!result.value) return
  const text = JSON.stringify(result.value.structured_data, null, 2)
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.warning('复制失败,请手动复制')
  }
}

onMounted(() => {
  const token = localStorage.getItem('token')
  if (token) loadHistory()
})
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
}
.type-selector { margin-bottom: 16px; }
.upload-area {
  :deep(.el-upload) { width: 100%; }
  :deep(.el-upload-dragger) {
    width: 100%;
    height: 280px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
.upload-placeholder {
  text-align: center;
  .upload-text { font-size: 16px; color: #606266; margin-top: 12px; }
  .upload-hint { font-size: 12px; color: #909399; margin-top: 6px; }
}
.preview-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  .preview-img { max-width: 100%; max-height: 250px; border-radius: 4px; }
  .preview-actions { position: absolute; bottom: 8px; right: 8px; }
}
.action-bar {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  .file-info { color: #909399; font-size: 13px; }
}
.meta-row {
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
}
.result-content {
  h4 { margin: 20px 0 10px; color: #303133; font-size: 15px; padding-left: 8px; border-left: 3px solid #409EFF; }
  h5 { margin: 12px 0 8px; color: #606266; font-size: 14px; }
}
.structured { margin-bottom: 16px; }
.diag-highlight {
  color: #f56c6c;
  font-weight: 600;
}
.abnormal { color: #f56c6c; font-weight: 600; }
.flag { color: #f56c6c; font-weight: 700; margin-left: 4px; }
.result-cell.high { color: #f56c6c; font-weight: 600; background: #fef0f0; padding: 2px 6px; border-radius: 3px; }
.result-cell.low { color: #409EFF; font-weight: 600; background: #f0f9ff; padding: 2px 6px; border-radius: 3px; }
.abnormal-count { color: #f56c6c; font-weight: 500; font-size: 12px; margin-left: 4px; }

// 智能解析视图
.parsed-text {
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
}
.parsed-section {
  margin-bottom: 12px;
  h5 { margin: 8px 0; color: #303133; font-size: 13px; font-weight: 600; }
}
.header-section {
  text-align: center;
  padding: 8px 0;
  border-bottom: 1px solid #ebeef5;
  .header-line {
    font-size: 14px;
    color: #303133;
    font-weight: 600;
    line-height: 1.8;
  }
}
.footer-section {
  background: #f5f7fa;
  padding: 10px 12px;
  border-radius: 4px;
  border-left: 3px solid #909399;
  .footer-line {
    font-size: 12px;
    color: #606266;
    line-height: 1.8;
  }
}
.test-table {
  font-size: 12px;
  :deep(.el-table__row) td { padding: 6px 0; }
}

.raw-collapse {
  margin-top: 12px;
  :deep(.el-collapse-item__header) {
    font-size: 13px;
    color: #909399;
  }
}
.raw-text-plain {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  color: #606266;
  max-height: 250px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: monospace;
}
.instructions, .summary {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fdf6ec;
  border-left: 3px solid #E6A23C;
  border-radius: 4px;
  font-size: 13px;
  line-height: 1.6;
}

.action-buttons {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 12px;
  justify-content: center;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
  display: flex;
}
</style>
