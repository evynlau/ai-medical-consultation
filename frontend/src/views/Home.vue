<template>
  <div class="home page-container">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-content">
        <h1>AI 智能问诊 <span class="highlight">7×24h</span> 健康守护</h1>
        <p class="subtitle">基于 LLM + 医学知识库 + Agent 智能体,<br/>随时为您提供专业的健康咨询服务</p>
        <div class="actions">
          <el-button type="primary" size="large" @click="$router.push('/chat')">
            <el-icon><Promotion /></el-icon>
            立即开始问诊
          </el-button>
          <el-button size="large" @click="$router.push('/knowledge')">浏览知识库</el-button>
        </div>
      </div>
      <div class="hero-icon">
        <el-icon :size="160" color="#409EFF" :stroke-width="1.5"><FirstAidKit /></el-icon>
      </div>
    </section>

    <!-- 功能卡片 -->
    <section class="features">
      <el-row :gutter="20">
        <el-col :xs="24" :sm="12" :md="8" v-for="f in features" :key="f.title">
          <el-card class="feature-card" shadow="hover">
            <div class="feature-icon" :style="{ background: f.bg }">
              <el-icon :size="32" color="#fff"><component :is="f.icon" /></el-icon>
            </div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
          </el-card>
        </el-col>
      </el-row>
    </section>

    <!-- 快速入口 -->
    <section class="quick">
      <h2>常见症状快速咨询</h2>
      <div class="symptom-tags">
        <el-tag
          v-for="s in commonSymptoms"
          :key="s"
          size="large"
          effect="plain"
          class="symptom-tag"
          @click="quickAsk(s)"
        >
          {{ s }}
        </el-tag>
      </div>
    </section>

    <!-- 免责声明 -->
    <el-alert
      class="disclaimer"
      type="warning"
      :closable="false"
      show-icon
      title="重要提醒"
      description="本系统提供的所有健康建议仅供参考,不能替代专业医生的面诊和检查。如出现紧急情况(剧烈胸痛、呼吸困难、大出血、意识障碍等),请立即拨打 120 或前往最近的医院急诊。"
    />
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const chatStore = useChatStore()

const features = [
  { title: '智能问诊', desc: '多轮对话收集症状,AI 分析可能病因', icon: 'ChatLineSquare', bg: 'linear-gradient(135deg, #409EFF, #2c7be5)' },
  { title: '影像分析', desc: 'AI 辅助识别胸片病灶,Grad-CAM 可视化', icon: 'Picture', bg: 'linear-gradient(135deg, #9c27b0, #7b1fa2)' },
  { title: 'OCR 识别', desc: '处方/检查报告智能识别与结构化', icon: 'Files', bg: 'linear-gradient(135deg, #00bcd4, #0097a7)' },
  { title: '知识库检索', desc: '基于向量数据库的医学知识精准检索', icon: 'Reading', bg: 'linear-gradient(135deg, #67C23A, #5daf34)' },
  { title: '智能分诊', desc: '根据症状推荐就诊科室,判断紧急程度', icon: 'Files', bg: 'linear-gradient(135deg, #E6A23C, #cf9236)' },
  { title: '诊断建议', desc: '给出可能病因、检查建议、护理指导', icon: 'Document', bg: 'linear-gradient(135deg, #F56C6C, #dd6161)' },
  { title: '问诊记录', desc: '持久化存储问诊历史,支持回溯查看', icon: 'Clock', bg: 'linear-gradient(135deg, #909399, #82848a)' },
  { title: '紧急识别', desc: '检测紧急症状,优先提示就医', icon: 'WarningFilled', bg: 'linear-gradient(135deg, #ff6b6b, #ee5a52)' }
]

const commonSymptoms = [
  '头痛', '发热', '咳嗽', '腹痛', '腹泻', '胸痛',
  '心悸', '失眠', '过敏', '皮疹', '咽痛', '乏力'
]

const quickAsk = async (symptom) => {
  await chatStore.startConsultation(`最近${symptom},请帮我分析一下`)
  router.push('/chat')
}
</script>

<style lang="scss" scoped>
.hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 40px 0;
  gap: 40px;

  h1 {
    font-size: 36px;
    margin: 0 0 16px;
    color: #303133;
    .highlight { color: #409EFF; }
  }
  .subtitle { font-size: 16px; color: #606266; line-height: 1.8; margin: 0 0 24px; }
  .actions { display: flex; gap: 12px; }
  .hero-icon { flex-shrink: 0; opacity: 0.85; }
}

@media (max-width: 768px) {
  .hero { flex-direction: column; text-align: center; }
  .actions { justify-content: center; }
}

.features { margin: 32px 0; }
.feature-card {
  text-align: center;
  padding: 20px 0;
  height: 200px;
  border-radius: 8px;
  transition: transform 0.2s;

  &:hover { transform: translateY(-4px); }

  .feature-icon {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    margin: 0 auto 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  h3 { margin: 0 0 8px; font-size: 16px; }
  p { color: #909399; font-size: 13px; margin: 0; line-height: 1.6; }
}

.quick {
  margin: 40px 0;
  h2 { font-size: 22px; margin-bottom: 20px; }
  .symptom-tags { display: flex; flex-wrap: wrap; gap: 10px; }
  .symptom-tag { cursor: pointer; padding: 8px 16px; }
}

.disclaimer { margin: 32px 0 16px; }
</style>
