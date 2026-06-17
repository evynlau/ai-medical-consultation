<template>
  <div class="chat-page page-container">
    <PageHero
      badge="多轮对话 · 知识库参考 · 紧急度自动识别"
      title="智能问诊"
      subtitle="描述您的不适,AI 多轮追问后给出可能病因、推荐科室与自我护理建议。"
      :icon="ChatLineSquare"
      :variant="1"
    />

    <el-card shadow="never" class="chat-card">
      <!-- 顶部信息 -->
      <div class="chat-header">
        <div>
          <h3>
            <el-icon><ChatLineSquare /></el-icon>
            <el-tooltip
              v-if="chatStore.currentConsultation?.chief_complaint"
              :content="chatStore.currentConsultation.chief_complaint"
              placement="bottom"
              :show-after="300"
            >
              <span class="truncate-title">
                {{ truncatedChiefComplaint }}
              </span>
            </el-tooltip>
            <span v-else>新问诊</span>
          </h3>
          <div class="meta" v-if="chatStore.currentConsultation">
            <el-tag size="small" :type="urgencyType(chatStore.currentConsultation.urgency_level)">
              紧急度: {{ urgencyLabel(chatStore.currentConsultation.urgency_level) }}
            </el-tag>
            <el-tag v-if="chatStore.currentConsultation.recommended_department" size="small" type="success" effect="plain">
              <el-icon><Files /></el-icon> {{ chatStore.currentConsultation.recommended_department }}
            </el-tag>
            <el-tag size="small" effect="plain">{{ messageCount }} 条消息</el-tag>
          </div>
        </div>
        <div>
          <el-button v-if="!chatStore.isInConsultation" type="primary" @click="showStart = true">
            开始新问诊
          </el-button>
          <el-button v-else @click="showAnalyze = true" type="warning" plain>
            <el-icon><DataAnalysis /></el-icon>
            结构化分析
          </el-button>
          <el-button @click="handleClear">清空</el-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="messages" ref="messagesRef">
        <template v-if="!chatStore.isInConsultation">
          <el-empty description='还没有问诊，点击右上角「开始新问诊」或描述您的症状开始' />
        </template>

        <template v-else>
          <div
            v-for="msg in chatStore.messages"
            :key="msg.id"
            class="chat-message"
            :class="msg.role === 'user' ? 'user' : (msg.role === 'doctor' ? 'doctor' : 'ai')"
          >
            <div
              class="chat-avatar"
              :class="msg.role === 'user' ? 'user' : (msg.role === 'doctor' ? 'doctor' : 'ai')"
            >
              <el-icon :size="20">
                <component
                  :is="msg.role === 'user' ? 'User' : (msg.role === 'doctor' ? 'UserFilled' : 'FirstAidKit')"
                />
              </el-icon>
            </div>
            <div>
              <!-- 医生回复:气泡上方加身份标识 -->
              <div v-if="msg.role === 'doctor'" class="doctor-tag">
                <el-icon><UserFilled /></el-icon>
                医生回复
              </div>
              <div
                class="chat-bubble"
                :class="msg.role === 'user' ? 'user' : (msg.role === 'doctor' ? 'doctor' : 'ai')"
              >
                <!-- 紧急提示 -->
                <div v-if="msg.urgency_level && msg.urgency_level >= 4" class="emergency-alert">
                  <el-icon><WarningFilled /></el-icon>
                  检测到可能的紧急症状,建议立即就医或拨打 120
                </div>
                <!-- 内容(Markdown 渲染) -->
                <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                <!-- 知识来源(仅 AI 消息显示;医生回复不再标注参考) -->
                <div
                  v-if="msg.role !== 'doctor' && msg.source_knowledge && msg.source_knowledge.length"
                  class="knowledge-sources"
                >
                  <div class="source-title">📚 参考医学知识</div>
                  <div
                    v-for="(src, i) in msg.source_knowledge"
                    :key="i"
                    class="source-item"
                    @click="viewSource(src)"
                  >
                    {{ i + 1 }}. {{ src.title || src.id }}
                    <span class="source-meta">
                      [{{ src.category }}] 相关度 {{ (src.relevance || src.score || 0).toFixed(2) }}
                    </span>
                  </div>
                </div>
                <!-- 时间 -->
                <div class="msg-time">{{ formatTime(msg.created_at) }}</div>
              </div>
            </div>
          </div>

          <!-- loading 提示 -->
          <div v-if="chatStore.isLoading" class="chat-message ai">
            <div class="chat-avatar ai">
              <el-icon :size="20"><FirstAidKit /></el-icon>
            </div>
            <div class="chat-bubble ai">
              <el-icon class="is-loading"><Loading /></el-icon>
              AI 正在思考...
            </div>
          </div>
        </template>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          :placeholder="chatStore.isInConsultation ? '继续描述症状、追问或要求建议…' : '请先开始新问诊'"
          :disabled="!chatStore.isInConsultation || chatStore.isLoading"
          @keydown.enter.exact.prevent="handleSend"
          resize="none"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="chatStore.isLoading"
          :disabled="!inputText.trim() || !chatStore.isInConsultation"
          @click="handleSend"
        >
          发送
        </el-button>
      </div>
    </el-card>

    <!-- 开始问诊对话框 -->
    <el-dialog v-model="showStart" title="开始新问诊" width="600px">
      <el-form :model="startForm" label-width="80px">
        <!-- 携带的 OCR/报告上下文 -->
        <el-alert
          v-if="pendingContext"
          :title="`📋 已携带${pendingContext.summary}`"
          type="success"
          :closable="true"
          @close="chatStore.pendingContext = null"
          style="margin-bottom: 12px"
          show-icon
        >
          <div style="font-size: 12px; color: #606266">
            完整报告已附加在主诉中,直接点"开始"即可
          </div>
        </el-alert>

        <el-form-item label="主诉">
          <el-input
            v-model="startForm.complaint"
            type="textarea"
            :rows="6"
            placeholder="请用一两句话描述您的主要不适,例如:头痛 3 天,伴有低烧"
          />
        </el-form-item>

        <!-- OCR 报告内容预览(可折叠) -->
        <el-form-item v-if="pendingContext" label="报告预览">
          <div class="ocr-preview">
            <el-button type="primary" link size="small" @click="showOcrPreview = !showOcrPreview">
              <el-icon><component :is="showOcrPreview ? 'View' : 'Hide'" /></el-icon>
              {{ showOcrPreview ? '收起完整内容' : '展开查看完整报告' }}
              ({{ pendingContext.content.length }} 字)
            </el-button>
            <pre v-show="showOcrPreview" class="ocr-content">{{ pendingContext.content }}</pre>
          </div>
        </el-form-item>
        <el-form-item label="示例">
          <div class="examples">
            <el-tag
              v-for="ex in examples"
              :key="ex"
              class="example-tag"
              @click="startForm.complaint = ex"
            >{{ ex }}</el-tag>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showStart = false">取消</el-button>
        <el-button type="primary" :disabled="!startForm.complaint.trim()" @click="handleStart">
          开始
        </el-button>
      </template>
    </el-dialog>

    <!-- 结构化分析结果 -->
    <el-dialog v-model="showAnalyze" title="症状结构化分析" width="640px">
      <div v-if="analyzeResult">
        <el-alert
          v-if="analyzeResult.needs_urgent_care"
          type="error"
          :closable="false"
          show-icon
          title="⚠️ 紧急提示"
          description="检测到可能的紧急症状,请立即就医或拨打 120"
        />
        <el-descriptions :column="1" border style="margin-top: 12px">
          <el-descriptions-item label="紧急程度">
            <el-tag :type="urgencyType(analyzeResult.urgency_level)">
              {{ urgencyLabel(analyzeResult.urgency_level) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="推荐科室">
            {{ analyzeResult.department || '暂无' }}
          </el-descriptions-item>
          <el-descriptions-item label="可能原因">
            <el-tag
              v-for="c in (analyzeResult.possible_causes || [])"
              :key="c"
              style="margin: 2px"
            >{{ c }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="建议检查">
            <div v-for="e in (analyzeResult.suggested_examinations || [])" :key="e">• {{ e }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="自我护理">
            <div v-for="t in (analyzeResult.self_care_tips || [])" :key="t">• {{ t }}</div>
          </el-descriptions-item>
          <el-descriptions-item label="参考来源" v-if="analyzeResult.reference_sources?.length">
            <div
              v-for="(s, i) in analyzeResult.reference_sources"
              :key="i"
              style="font-size: 13px; color: #606266"
            >
              {{ i + 1 }}. {{ s.title }} [{{ s.category }}] 相关度 {{ s.relevance }}
            </div>
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          type="info"
          :closable="false"
          style="margin-top: 12px"
          title="免责声明"
          description="本分析仅供参考,不能替代专业医生诊断。如有不适,请及时就医。"
        />
      </div>
      <div v-else>
        <el-skeleton :rows="6" animated />
      </div>
    </el-dialog>

    <!-- 知识详情弹窗(Markdown 渲染) -->
    <el-dialog
      v-model="showKbDetail"
      :title="kbDetail?.title || '医学知识详情'"
      width="780px"
      top="5vh"
      class="kb-detail-dialog"
      destroy-on-close
    >
      <div v-if="kbDetail" v-loading="kbLoading">
        <!-- 元信息条 -->
        <div class="kb-meta">
          <el-tag size="small" :type="kbCategoryType(kbDetail.category)">
            {{ kbCategoryLabel(kbDetail.category) }}
          </el-tag>
          <span v-if="kbDetail.tags" class="kb-tags">
            <el-icon><CollectionTag /></el-icon>
            {{ kbDetail.tags }}
          </span>
          <span v-if="kbDetail.source" class="kb-source">
            <el-icon><Document /></el-icon>
            {{ kbDetail.source }}
          </span>
          <span class="kb-date">
            <el-icon><Clock /></el-icon>
            {{ formatTime(kbDetail.created_at) }}
          </span>
        </div>

        <!-- Markdown 正文 -->
        <div class="markdown-body kb-content" v-html="renderMarkdown(kbDetail.content)"></div>
      </div>
      <div v-else>
        <el-skeleton :rows="8" animated />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CollectionTag, Document, Clock } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { useChatStore } from '@/stores/chat'
import { agentApi } from '@/api/agent'
import { knowledgeApi } from '@/api/knowledge'
import PageHero from '@/components/PageHero.vue'

const route = useRoute()
const chatStore = useChatStore()
const messagesRef = ref(null)
const inputText = ref('')
const showStart = ref(false)
const showAnalyze = ref(false)
const analyzeResult = ref(null)

const startForm = ref({ complaint: '' })
const examples = [
  '头痛 3 天,伴有低烧 37.8°C',
  '最近 1 周咳嗽,有黄痰',
  '胃痛,饭后加重,反酸',
  '血压偏高 150/95,偶尔头晕',
  '皮肤出现红色疹子,瘙痒'
]

// OCR / 报告上下文(从 OCR 页跳过来时携带)
const pendingContext = computed(() => chatStore.pendingContext)
const showContextBanner = ref(false)
const showOcrPreview = ref(false)  // 展开/收起完整报告预览
watch(pendingContext, (v) => {
  if (v) {
    showContextBanner.value = true
    // 主诉框 = 短标题(给用户直接看到),但实际上传给后端的是完整内容
    // 这样:
    //  - 顶部标题干净(短标题)
    //  - 主诉框不撑爆(短标题)
    //  - 完整报告 = 完整内容,作为后端 chief_complaint 入库
    //  - AI 拿到完整上下文
    startForm.value.complaint = v.title || v.content
    showOcrPreview.value = false  // 默认折叠
  }
}, { immediate: true })

// 标题过长截断显示(> 30 字加尾缀)
const truncatedChiefComplaint = computed(() => {
  const c = chatStore.currentConsultation?.chief_complaint || ''
  return c.length > 30 ? c.slice(0, 30) + '...' : c
})

const messageCount = computed(() => chatStore.messages.length)

marked.setOptions({ breaks: true, gfm: true })
const renderMarkdown = (text) => {
  if (!text) return ''
  return marked.parse(text)
}

const formatTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
}

const urgencyLabel = (level) => {
  return ['', '无需就医', '择期就医', '尽快就医', '立即急诊'][level || 1] || '未知'
}
const urgencyType = (level) => ['', 'info', 'success', 'warning', 'danger'][level || 1] || 'info'

// 知识分类
const kbCategoryLabel = (c) => ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c || '其他')
const kbCategoryType = (c) => ({ disease: 'danger', drug: 'warning', examination: 'success', guideline: 'info' }[c] || '')

// 滚动到底部
const scrollToBottom = async () => {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

watch(() => chatStore.messages.length, scrollToBottom)

onMounted(async () => {
  // 从路由加载历史问诊
  const id = route.params.id
  if (id) {
    try {
      await chatStore.loadConsultation(Number(id))
      scrollToBottom()
    } catch (e) {
      ElMessage.error('加载问诊失败')
    }
  }
})

const handleStart = async () => {
  if (!startForm.value.complaint.trim()) return
  showStart.value = false
  try {
    // chief_complaint 取完整报告(让 AI 有完整上下文)
    // 顶部标题显示是后端返回的 chief_complaint,我们已在前端用 tooltip + 截断双管齐下
    const chiefComplaint = chatStore.pendingContext?.content
      || startForm.value.complaint.trim()
    await chatStore.startConsultation(chiefComplaint)
    startForm.value.complaint = ''
    // 启动后清掉 pendingContext(已用完)
    chatStore.pendingContext = null
    scrollToBottom()
  } catch (e) {
    ElMessage.error('创建问诊失败')
  }
}

const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  try {
    await chatStore.sendMessage(text)
    scrollToBottom()
  } catch (e) {
    ElMessage.error('发送失败')
  }
}

const handleClear = () => {
  ElMessageBox.confirm('确认清空当前问诊?', '提示', { type: 'warning' })
    .then(() => chatStore.clearCurrent())
    .catch(() => {})
}

// 结构化分析
const runAnalyze = async () => {
  if (!chatStore.currentConsultation) {
    ElMessage.warning('请先开始问诊')
    return
  }
  showAnalyze.value = true
  analyzeResult.value = null
  try {
    const chief = chatStore.currentConsultation.chief_complaint
    const allText = chatStore.messages
      .filter((m) => m.role === 'user')
      .map((m) => m.content)
      .join('\n')
    const result = await agentApi.analyze({
      symptoms: allText || chief,
      consultation_id: chatStore.currentConsultationId
    })
    analyzeResult.value = result
    // 刷新当前问诊的紧急度/科室
    await chatStore.loadConsultation(chatStore.currentConsultationId)
    ElMessage.success('已同步到问诊记录,管理后台可看到紧急度')
  } catch (e) {
    ElMessage.error('分析失败')
    showAnalyze.value = false
  }
}

watch(showAnalyze, (v) => { if (v) runAnalyze() })

// 知识详情弹窗
const showKbDetail = ref(false)
const kbDetail = ref(null)
const kbLoading = ref(false)
const viewSource = async (src) => {
  if (!src.id) return
  showKbDetail.value = true
  kbDetail.value = null
  kbLoading.value = true
  try {
    kbDetail.value = await knowledgeApi.detail(src.id)
  } catch {
    ElMessage.error('加载知识详情失败')
    showKbDetail.value = false
  } finally {
    kbLoading.value = false
  }
}
</script>

<style lang="scss" scoped>
.chat-card { border-radius: 8px; }
.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 16px;
  h3 { margin: 0 0 8px; display: flex; align-items: center; gap: 6px; font-size: 16px; }
  .meta { display: flex; gap: 8px; flex-wrap: wrap; }
}

.messages {
  height: 500px;
  overflow-y: auto;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  margin-bottom: 16px;
}

.input-area {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  :deep(.el-textarea__inner) { resize: none; }
}

// OCR 报告预览
.ocr-preview {
  width: 100%;
}
.ocr-content {
  margin: 8px 0 0;
  padding: 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  color: #303133;
  font-family: 'Courier New', Consolas, monospace;
}

// 顶部标题过长截断
.truncate-title {
  display: inline-block;
  max-width: 600px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}

.msg-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 6px;
  text-align: right;
}

.examples { display: flex; flex-wrap: wrap; gap: 6px; }
.example-tag { cursor: pointer; }

/* ========== 知识详情弹窗 ========== */
.kb-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 14px;
  margin-bottom: 16px;
  background: #f5f7fa;
  border-radius: 6px;
  font-size: 13px;
  color: #606266;

  > span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .el-icon { color: #909399; }
}

.kb-content {
  max-height: 60vh;
  overflow-y: auto;
  padding: 8px 4px 24px;
  font-size: 14px;
  line-height: 1.8;
  color: #303133;

  h1, h2, h3, h4 {
    margin: 18px 0 10px;
    font-weight: 600;
    color: #303133;
    border-left: 3px solid #409EFF;
    padding-left: 10px;
  }
  h1 { font-size: 18px; }
  h2 { font-size: 16px; }
  h3 { font-size: 15px; border-left-color: #67C23A; }
  h4 { font-size: 14px; border-left-color: #E6A23C; border-left-width: 2px; }

  p { margin: 8px 0; }
  ul, ol { padding-left: 24px; margin: 8px 0; }
  li { margin: 4px 0; line-height: 1.7; }

  /* 列表项里的关键词高亮 */
  li::marker { color: #409EFF; }

  /* 表格(知识库里的"项目/结果/参考"那种) */
  table {
    border-collapse: collapse;
    width: 100%;
    margin: 12px 0;
    font-size: 13px;
    background: #fff;
    border-radius: 4px;
    overflow: hidden;
    box-shadow: 0 0 0 1px #ebeef5;
  }
  th, td {
    padding: 8px 12px;
    border: 1px solid #ebeef5;
    text-align: left;
  }
  th {
    background: #f5f7fa;
    font-weight: 600;
    color: #303133;
  }
  tr:nth-child(even) td { background: #fafbfc; }

  /* 强调文本 */
  strong { color: #f56c6c; font-weight: 600; }
  em { color: #409EFF; font-style: normal; }

  /* 代码块 */
  code {
    background: #f0f2f5;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
    color: #d63384;
  }
  pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12px 14px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 13px;
    line-height: 1.6;
    code { background: transparent; color: inherit; padding: 0; }
  }

  /* 引用 */
  blockquote {
    border-left: 3px solid #c0c4cc;
    padding: 6px 12px;
    margin: 10px 0;
    color: #606266;
    background: #fafafa;
  }

  /* 水平线 */
  hr { border: 0; border-top: 1px dashed #dcdfe6; margin: 16px 0; }
}
</style>
