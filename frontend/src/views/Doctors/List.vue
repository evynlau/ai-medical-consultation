<template>
  <div class="doctor-page">
    <!-- ============== 顶部 Hero ============== -->
    <section class="hero">
      <div class="hero-deco hero-deco-1"></div>
      <div class="hero-deco hero-deco-2"></div>
      <div class="hero-deco hero-deco-3"></div>

      <div class="hero-inner">
        <div class="hero-text">
          <div class="hero-eyebrow">
            <span class="pulse"></span>
            <span>智能匹配 · 语义检索 · 多维筛选</span>
          </div>
          <h1 class="hero-title">
            找对医生,<br>
            从 <span class="accent">一次智能检索</span> 开始
          </h1>
          <p class="hero-subtitle">
            基于科室、医院、疾病、城市多维度筛选,也可直接用自然语言描述你的需求,
            系统会为你匹配最合适的医生。
          </p>

          <div class="hero-stats">
            <div class="stat-cell">
              <div class="stat-num">{{ stats.doctors ?? '—' }}</div>
              <div class="stat-lbl">位名医</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-cell">
              <div class="stat-num">{{ stats.hospitals ?? '—' }}</div>
              <div class="stat-lbl">家医院</div>
            </div>
            <div class="stat-divider"></div>
            <div class="stat-cell">
              <div class="stat-num">{{ stats.departments ?? '—' }}</div>
              <div class="stat-lbl">个科室</div>
            </div>
          </div>
        </div>

        <div class="hero-visual">
          <div class="ring ring-1"></div>
          <div class="ring ring-2"></div>
          <div class="ring ring-3"></div>
          <el-icon class="center-icon" :size="80" color="#fff"><UserFilled /></el-icon>
        </div>
      </div>
    </section>

    <!-- ============== 智能问答框 ============== -->
    <section class="ai-section">
      <div class="ai-search">
        <div class="ai-label">
          <el-icon :size="20" color="#fff"><MagicStick /></el-icon>
          智能问答
        </div>
        <el-input
          v-model="aiQuery"
          placeholder="试试:苏州治肝癌的医生 / 上海擅长糖尿病的主任医师 / 儿童血液病专家"
          clearable
          size="large"
          @keyup.enter="aiSearch"
        >
          <template #append>
            <el-button type="primary" :loading="aiLoading" size="large" @click="aiSearch">
              <el-icon><Search /></el-icon> 问名医
            </el-button>
          </template>
        </el-input>
      </div>

      <div class="example-pills">
        <span class="pill-label">试试:</span>
        <span
          v-for="q in exampleQueries"
          :key="q"
          class="example-pill"
          @click="quickAsk(q)"
        >{{ q }}</span>
      </div>
    </section>

    <!-- ============== 热门入口(快速跳转) ============== -->
    <section v-if="hotHospitals.length || hotDepartments.length" class="hot-section">
      <div class="hot-block" v-if="hotHospitals.length">
        <div class="hot-title">
          <el-icon><OfficeBuilding /></el-icon>
          <span>热门医院</span>
        </div>
        <div class="hot-items">
          <span
            v-for="h in hotHospitals"
            :key="h"
            class="hot-pill"
            @click="quickFilterHospital(h)"
          >{{ h }} <small>({{ countByHospital[h] }})</small></span>
        </div>
      </div>
      <div class="hot-block" v-if="hotDepartments.length">
        <div class="hot-title">
          <el-icon><FirstAidKit /></el-icon>
          <span>热门科室</span>
        </div>
        <div class="hot-items">
          <span
            v-for="d in hotDepartments"
            :key="d"
            class="hot-pill"
            @click="quickFilterDepartment(d)"
          >{{ d }} <small>({{ countByDepartment[d] }})</small></span>
        </div>
      </div>
    </section>

    <!-- ============== 筛选条 + 列表 ============== -->
    <section class="filter-section">
      <div class="filter-bar">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索医生姓名 / 简介"
          clearable
          size="default"
          style="flex: 1; min-width: 220px"
          @change="onFilterChange"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>

        <el-select
          v-model="filters.department"
          clearable
          placeholder="科室"
          style="width: 160px"
          @change="onFilterChange"
        >
          <el-option v-for="d in allDepartments" :key="d" :label="d" :value="d" />
        </el-select>

        <el-select
          v-model="filters.hospital"
          clearable
          placeholder="医院"
          style="width: 220px"
          filterable
          @change="onFilterChange"
        >
          <el-option v-for="h in allHospitals" :key="h" :label="h" :value="h" />
        </el-select>

        <el-input
          v-model="filters.disease"
          placeholder="擅长疾病"
          clearable
          style="width: 160px"
          @change="onFilterChange"
        />

        <el-input
          v-model="filters.city"
          placeholder="城市"
          clearable
          style="width: 120px"
          @change="onFilterChange"
        />

        <el-button @click="resetFilter" plain>
          <el-icon><RefreshLeft /></el-icon> 重置
        </el-button>
      </div>

      <div class="result-meta">
        <div class="meta-left">
          <span v-if="mode === 'filter'">共找到 <strong>{{ total }}</strong> 位医生</span>
          <div v-else class="ai-banner">
            <el-icon><ChatLineRound /></el-icon>
            <span>正在显示 <strong>{{ total }}</strong> 条「<strong>{{ lastQuery }}</strong>」的语义检索结果</span>
            <el-button link type="primary" @click="resetAi">
              <el-icon><RefreshLeft /></el-icon> 清空 AI,回到筛选
            </el-button>
          </div>
        </div>
        <el-pagination
          v-if="mode === 'filter' && total > size"
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          :page-sizes="[12, 24, 48]"
          layout="sizes, prev, pager, next, jumper"
          background
          @current-change="load"
          @size-change="load"
        />
      </div>
    </section>

    <!-- ============== 医生卡片网格 ============== -->
    <section class="doctor-grid" v-loading="loading">
      <el-empty v-if="!loading && items.length === 0" description="暂无医生信息,试试调整筛选或清空智能问答" />
      <div v-else class="card-grid">
        <div
          v-for="d in items"
          :key="d.id"
          class="doctor-card"
          :class="mode === 'ai' ? 'is-ai' : ''"
          @click="goDetail(d.id)"
        >
          <el-avatar :size="56" :src="d.avatar" class="avatar">
            {{ d.name?.[0] }}
          </el-avatar>

          <div class="info">
            <div class="name-line">
              <h3 class="name">{{ d.name }}</h3>
              <el-tag v-if="d.title" size="small" type="warning" effect="light">
                {{ d.title.split(/[、，,]/)[0] }}
              </el-tag>
              <el-tag v-if="mode === 'ai' && d.score !== undefined" size="small" type="success" effect="light" class="relevance">
                相关度 {{ (d.score * 100).toFixed(0) }}%
              </el-tag>
            </div>

            <div class="row2">
              <span><el-icon><FirstAidKit /></el-icon> {{ d.department }}</span>
              <span class="dot">·</span>
              <span><el-icon><OfficeBuilding /></el-icon> {{ d.hospital }}</span>
              <span v-if="d.city" class="city">{{ d.city }}</span>
            </div>

            <div v-if="d.diseases" class="diseases">
              <span
                v-for="x in d.diseases.split(',').slice(0, 4)"
                :key="x"
                class="disease-tag"
              >{{ x.trim() }}</span>
              <span v-if="d.diseases.split(',').length > 4" class="disease-more">
                +{{ d.diseases.split(',').length - 4 }}
              </span>
            </div>
          </div>

          <div class="card-arrow">
            <el-icon><ArrowRight /></el-icon>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { doctorApi } from '@/api/doctor'

const router = useRouter()

// ===== 列表加载 =====
// 列表只渲染「当前选中模式」的 items:筛选模式 = 后端筛选结果;
// AI 模式 = 语义检索结果。两者不会同时显示。
const items = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const size = ref(12)
const filters = reactive({ keyword: '', department: '', hospital: '', disease: '', city: '' })
const mode = ref('filter')  // 'filter' | 'ai':决定 items 来自筛选还是 AI

// ===== 统计/热门(只算一次,放在 loadStats 里) =====
const stats = reactive({ doctors: 0, hospitals: 0, departments: 0 })
const countByHospital = reactive({})
const countByDepartment = reactive({})
const allHospitals = computed(() => Object.keys(countByHospital).sort())
const allDepartments = computed(() => Object.keys(countByDepartment).sort())
const hotHospitals = computed(() =>
  Object.entries(countByHospital).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([h]) => h)
)
const hotDepartments = computed(() =>
  Object.entries(countByDepartment).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([d]) => d)
)

// ===== 智能问答 =====
const aiQuery = ref('')
const aiLoading = ref(false)
const aiResults = ref([])
const lastQuery = ref('')
const exampleQueries = [
  '苏州治肝癌的医生',
  '擅长糖尿病',
  '儿童血液病',
  '全飞秒激光手术',
  '试管婴儿',
  '腰椎间盘突出',
]

// ===== 列表加载(筛选模式) =====
const load = async () => {
  loading.value = true
  try {
    const res = await doctorApi.list({
      ...filters,
      page: page.value,
      size: size.value,
    })
    items.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

// 全量统计:拉一次 size=100 用来计算「热门医院 / 热门科室 / 顶部统计」,
// 只在挂载时跑一次,后续筛选/重置都不再累加
// 注:后端 /doctors 接口 size 上限是 100(不是 200),传 200 会被 422 拒绝
const loadStats = async () => {
  try {
    const res = await doctorApi.list({ page: 1, size: 100 })
    Object.keys(countByHospital).forEach(k => delete countByHospital[k])
    Object.keys(countByDepartment).forEach(k => delete countByDepartment[k])
    res.items.forEach(d => {
      if (d.hospital) countByHospital[d.hospital] = (countByHospital[d.hospital] || 0) + 1
      if (d.department) countByDepartment[d.department] = (countByDepartment[d.department] || 0) + 1
    })
    stats.doctors = res.total
    stats.hospitals = Object.keys(countByHospital).length
    stats.departments = Object.keys(countByDepartment).length
    console.log('[Doctors] loadStats:', {
      total: res.total, hospitals: stats.hospitals, departments: stats.departments,
    })
  } catch (e) {
    console.error('[Doctors] loadStats 失败:', e)
  }
}

const onFilterChange = () => {
  mode.value = 'filter'  // 切回筛选模式
  aiResults.value = []   // 清掉 AI 结果
  lastQuery.value = ''
  page.value = 1
  load()
}

const resetFilter = () => {
  Object.assign(filters, { keyword: '', department: '', hospital: '', disease: '', city: '' })
  mode.value = 'filter'
  aiResults.value = []
  lastQuery.value = ''
  page.value = 1
  load()
}

const aiSearch = async () => {
  const q = aiQuery.value.trim()
  if (!q) return
  aiLoading.value = true
  mode.value = 'ai'   // 切到 AI 模式,items 会显示 aiResults
  page.value = 1
  try {
    const res = await doctorApi.search(q, 12)
    aiResults.value = res.results
    lastQuery.value = q
    items.value = res.results  // 同时塞进 items,共享同一个结果区
    total.value = res.results.length
    if (!res.results.length) ElMessage.info('未匹配到相关医生,试试换种问法')
  } finally {
    aiLoading.value = false
  }
}

const resetAi = () => {
  aiQuery.value = ''
  aiResults.value = []
  lastQuery.value = ''
  // 切回筛选模式,重新拉列表
  mode.value = 'filter'
  page.value = 1
  load()
}

const quickAsk = (q) => {
  aiQuery.value = q
  aiSearch()
}

const quickFilterHospital = (h) => {
  filters.hospital = h
  page.value = 1
  load()
  // 滚到列表
  setTimeout(() => {
    document.querySelector('.filter-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 100)
}

const quickFilterDepartment = (d) => {
  filters.department = d
  page.value = 1
  load()
  setTimeout(() => {
    document.querySelector('.filter-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 100)
}

const goDetail = (id) => router.push(`/doctors/${id}`)

onMounted(() => {
  load()
  loadStats()
})
</script>

<style lang="scss" scoped>
@use '@/styles/tokens.scss' as t;

.doctor-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: t.sp(8);
  padding-bottom: t.sp(16);
}

/* ============================================
   顶部 Hero
   ============================================ */
.hero {
  position: relative;
  background: linear-gradient(135deg, t.c('primary-700') 0%, t.c('primary-500') 100%);
  padding: t.sp(16) t.sp(8) t.sp(20);
  margin: -16px -16px 0;  // 顶到 layout 主区外
  overflow: hidden;
  border-radius: 0 0 t.r('2xl') t.r('2xl');
}
.hero-deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
}
.hero-deco-1 {
  width: 320px; height: 320px;
  background: radial-gradient(circle, rgba(255,255,255,0.10), transparent 70%);
  top: -100px; right: -80px;
}
.hero-deco-2 {
  width: 200px; height: 200px;
  background: radial-gradient(circle, rgba(255,255,255,0.08), transparent 70%);
  bottom: -60px; left: 30%;
}
.hero-deco-3 {
  width: 120px; height: 120px;
  border: 1px solid rgba(255,255,255,0.20);
  top: 40%; left: 8%;
}

.hero-inner {
  position: relative;
  z-index: 2;
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
  gap: t.sp(10);
  align-items: center;

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.20);
  border-radius: t.r('full');
  color: #fff;
  font-size: 13px;
  margin-bottom: t.sp(5);
  backdrop-filter: blur(8px);

  .pulse {
    width: 8px; height: 8px;
    background: #fff;
    border-radius: 50%;
    box-shadow: 0 0 0 0 rgba(255,255,255,0.6);
    animation: pulse 2s ease-out infinite;
  }
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(255,255,255,0.6); }
  70% { box-shadow: 0 0 0 10px rgba(255,255,255,0); }
  100% { box-shadow: 0 0 0 0 rgba(255,255,255,0); }
}

.hero-title {
  font-family: t.font("serif");
  font-size: clamp(32px, 4vw, 48px);
  font-weight: 700;
  color: #fff;
  line-height: 1.2;
  margin: 0 0 t.sp(4);

  .accent {
    background: linear-gradient(120deg, #FFE9C8, #FFD8A8);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
    padding-right: 4px;
  }
}
.hero-subtitle {
  color: rgba(255,255,255,0.85);
  font-size: 16px;
  line-height: 1.7;
  max-width: 540px;
  margin-bottom: t.sp(6);
}

.hero-stats {
  display: inline-flex;
  align-items: center;
  gap: t.sp(6);
  padding: t.sp(4) t.sp(6);
  background: rgba(255,255,255,0.10);
  border: 1px solid rgba(255,255,255,0.18);
  border-radius: t.r('lg');
  backdrop-filter: blur(10px);
}
.stat-cell { text-align: center; }
.stat-num {
  font-family: t.font("serif");
  font-size: 32px;
  font-weight: 700;
  color: #fff;
  line-height: 1;
}
.stat-lbl {
  color: rgba(255,255,255,0.75);
  font-size: 13px;
  margin-top: 4px;
}
.stat-divider {
  width: 1px;
  height: 36px;
  background: rgba(255,255,255,0.20);
}

.hero-visual {
  position: relative;
  width: 280px; height: 280px;
  margin: 0 auto;
}
.ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.18);
}
.ring-2 { transform: scale(0.7); }
.ring-3 { transform: scale(0.45); border-color: rgba(255,255,255,0.30); }

.center-icon {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  padding: 28px;
  background: linear-gradient(135deg, rgba(255,255,255,0.18), rgba(255,255,255,0.08));
  border: 1px solid rgba(255,255,255,0.25);
  border-radius: t.r('2xl');
  backdrop-filter: blur(10px);
}

/* ============================================
   智能问答
   ============================================ */
.ai-section {
  max-width: 1200px;
  margin: -32px auto 0;
  position: relative;
  z-index: 5;
  padding: 0 t.sp(6);
}

.ai-search {
  background: #fff;
  border-radius: t.r('xl');
  padding: t.sp(5) t.sp(6);
  box-shadow: t.shadow('lg');
  border: 1px solid t.c('border');
  display: flex;
  align-items: center;
  gap: t.sp(4);

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: stretch;
    gap: t.sp(3);
  }
}
.ai-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 16px;
  color: #fff;
  padding: 10px 16px;
  background: linear-gradient(135deg, t.c('primary-500'), t.c('primary-700'));
  border-radius: t.r('md');
  white-space: nowrap;
}

.example-pills {
  max-width: 1200px;
  margin: t.sp(4) auto 0;
  padding: 0 t.sp(6);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.pill-label {
  color: t.c('text-3');
  font-size: 13px;
}
.example-pill {
  display: inline-block;
  padding: 6px 14px;
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('full');
  font-size: 13px;
  color: t.c('text-2');
  cursor: pointer;
  transition: all t.dur("fast") t.ease("out");

  &:hover {
    background: t.c('primary-50');
    color: t.c('primary-700');
    border-color: t.c('primary-300');
    transform: translateY(-1px);
  }
}

/* ============================================
   热门入口
   ============================================ */
.hot-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 t.sp(6);
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: t.sp(5);

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
  }
}
.hot-block {
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('lg');
  padding: t.sp(4) t.sp(5);
}
.hot-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  color: t.c('text-1');
  margin-bottom: t.sp(3);
  font-size: 14px;

  .el-icon { color: t.c('primary-500'); }
}
.hot-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.hot-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: t.c('bg-soft');
  border-radius: t.r('md');
  font-size: 13px;
  color: t.c('text-2');
  cursor: pointer;
  transition: all t.dur("fast") t.ease("out");

  small { color: t.c('text-3'); font-size: 11px; }

  &:hover {
    background: t.c('primary-50');
    color: t.c('primary-700');
  }
}

/* ============================================
   AI 结果
   ============================================ */
.ai-result {
  max-width: 1200px;
  margin: 0 auto;
  padding: t.sp(5) t.sp(6);
  background: linear-gradient(135deg, t.c('primary-50') 0%, #fff 100%);
  border: 1px solid t.c('primary-100');
  border-radius: t.r('xl');
}
.ai-result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: t.sp(4);

  h3 {
    margin: 0 0 4px;
    font-size: 18px;
    color: t.c('text-1');
    display: flex; align-items: center; gap: 6px;
  }
  p { margin: 0; color: t.c('text-3'); font-size: 13px; }
}
.ai-card {
  display: flex;
  gap: t.sp(3);
  padding: t.sp(4);
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('lg');
  cursor: pointer;
  transition: all t.dur("fast") t.ease("out");
  margin-bottom: t.sp(3);

  &:hover {
    border-color: t.c('primary-500');
    box-shadow: t.shadow('md');
    transform: translateY(-2px);
  }
  .info { flex: 1; min-width: 0; }
  .row1 {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .name { font-weight: 600; color: t.c('text-1'); }
  .relevance {
    color: t.c('success');
    font-size: 12px;
    font-weight: 600;
  }
  .row2 { color: t.c('primary-600'); font-size: 13px; margin-bottom: 4px; }
  .snippet {
    color: t.c('text-2');
    font-size: 12px;
    line-height: 1.6;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
}

/* ============================================
   筛选条
   ============================================ */
.filter-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 t.sp(6);
}
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: t.sp(3);
  padding: t.sp(4) t.sp(5);
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('lg');
  box-shadow: t.shadow('sm');
  align-items: center;

  .el-input, .el-select { flex-shrink: 0; }
}

.result-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: t.sp(4) 0;
  color: t.c('text-2');
  font-size: 14px;
  gap: t.sp(4);

  strong { color: t.c('primary-700'); font-size: 16px; }
}
.meta-left { flex: 1; min-width: 0; }
.ai-banner {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: linear-gradient(135deg, t.c('primary-50') 0%, #fff 100%);
  border: 1px solid t.c('primary-100');
  border-radius: t.r('md');
  color: t.c('text-2');
  flex-wrap: wrap;

  .el-icon { color: t.c('primary-500'); }
}

/* ============================================
   医生卡片网格
   ============================================ */
.doctor-grid {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 t.sp(6);
}

.card-grid {
  display: grid;
  // 桌面 3 列;平板 2 列;手机 1 列。直接用 media query 强制 3 列,避免 auto-fill 在某些情况下退化成 1 列
  grid-template-columns: repeat(3, 1fr);
  gap: t.sp(4);

  @media (max-width: 960px) {
    grid-template-columns: repeat(2, 1fr);
  }
  @media (max-width: 600px) {
    grid-template-columns: 1fr;
  }
}

.doctor-card {
  display: flex;
  align-items: center;
  gap: t.sp(3);
  padding: t.sp(4) t.sp(4);
  background: #fff;
  border: 1px solid t.c('border');
  border-radius: t.r('xl');
  cursor: pointer;
  transition: all t.dur("base") t.ease("out");
  overflow: hidden;
  // 去掉之前的 min-width: 0 — 它让 grid 1fr 退化成最小,导致整个 grid 变 1 列

  &:hover {
    transform: translateY(-2px);
    box-shadow: t.shadow('md');
    border-color: t.c('primary-500');
    .card-arrow { color: t.c('primary-600'); transform: translateX(2px); }
  }

  &.is-ai {
    background: linear-gradient(135deg, t.c('primary-50') 0%, #fff 100%);
    border-color: t.c('primary-100');
  }
}

.avatar {
  flex-shrink: 0;
  border: 2px solid #fff;
  box-shadow: t.shadow('xs');
}

.info {
  flex: 1;
  min-width: 0;        // 让 info 在窄卡片中可压缩,长内容换行而非溢出
  overflow: hidden;
}

.name-line {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;

  .name {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
    color: t.c('text-1');
    line-height: 1.3;
  }
  .relevance { flex-shrink: 0; }
}

.row2 {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  color: t.c('text-2');
  font-size: 13px;
  margin-bottom: 8px;
  line-height: 1.5;

  .el-icon { color: t.c('primary-500'); font-size: 13px; }
  .dot { color: t.c('text-3'); }
  .city {
    padding: 0 6px;
    background: t.c('bg-soft');
    border-radius: t.r('sm');
    font-size: 11px;
    color: t.c('text-3');
  }
}

.diseases {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.disease-tag {
  display: inline-block;
  padding: 2px 8px;
  background: t.c('primary-50');
  color: t.c('primary-700');
  border-radius: t.r('sm');
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.disease-more {
  display: inline-block;
  padding: 2px 8px;
  color: t.c('text-3');
  font-size: 12px;
  align-self: center;
}

.card-arrow {
  flex-shrink: 0;
  color: t.c('text-3');
  font-size: 16px;
  transition: all t.dur("fast") t.ease("out");
  align-self: center;
}

/* ============================================
   过渡动画
   ============================================ */
.slide-down-enter-active, .slide-down-leave-active {
  transition: all t.dur("base") t.ease("out");
}
.slide-down-enter-from, .slide-down-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
