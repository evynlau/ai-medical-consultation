<template>
  <div class="kb-page">
    <!-- ============================================
         上方 2/3 检索区(把检索作为页面主角)
         ============================================ -->
    <section class="search-hero">
      <div class="search-deco search-deco-1" />
      <div class="search-deco search-deco-2" />

      <div class="search-inner">
        <div class="hero-eyebrow">
          <span class="pulse" />
          <span>{{ totalCount }} 条权威医学知识 · 持续更新</span>
        </div>

        <h1 class="search-title">
          检索 <span class="accent">医学知识库</span>
        </h1>
        <p class="search-subtitle">
          基于公开权威指南（中华医学会 / ESC / NCCN）的语义检索，
          <br />支持症状、疾病、药品、检查的模糊查询与多分类筛选。
        </p>

        <!-- 大输入框 -->
        <div class="search-bar" :class="{ active: inputFocused }">
          <el-icon class="search-bar-icon"><Search /></el-icon>
          <input
            ref="inputRef"
            v-model="searchText"
            class="search-input"
            type="text"
            placeholder="输入症状、疾病或药品，如「胸痛」「高血压」"
            @focus="inputFocused = true"
            @blur="inputFocused = false"
            @keydown.enter="handleSearch"
          />
          <button
            class="btn btn-primary search-btn"
            :disabled="!searchText.trim()"
            @click="handleSearch"
          >搜索</button>
        </div>

        <!-- 分类 chips -->
        <div class="category-chips">
          <button
            v-for="c in categories"
            :key="c.value || 'all'"
            class="chip"
            :class="{ active: filterCategory === c.value }"
            @click="setCategory(c.value)"
          >
            {{ c.label }}
          </button>
        </div>

        <!-- 推荐搜索 -->
        <div class="suggest-row" v-if="!searchMode">
          <span class="suggest-lbl">热门检索</span>
          <span
            v-for="kw in hotKeywords"
            :key="kw"
            class="symptom-pill"
            @click="quickSearch(kw)"
          >{{ kw }}</span>
        </div>
        <div class="suggest-row" v-else>
          <span class="suggest-lbl">检索模式</span>
          <span class="meta">
            关键词 "<b>{{ searchText }}</b>" · 命中
            <b>{{ searchResults.length }}</b> 条
          </span>
          <el-button text type="primary" @click="exitSearch">返回全部</el-button>
        </div>
      </div>
    </section>

    <!-- ============================================
         下方 1/3 结果区
         ============================================ -->
    <section class="result-section">
      <div class="result-header">
        <h3>{{ searchMode ? '语义检索结果' : '知识库列表' }}</h3>
        <span class="result-count" v-if="!searchMode">
          共 {{ pagination.total }} 条 · 第 {{ pagination.page }} / {{ totalPages }} 页
        </span>
      </div>

      <!-- 检索结果(卡片视图,语义匹配的高匹配度展示) -->
      <div v-if="searchMode" class="search-result-grid" v-loading="loading">
        <div
          v-for="(row, i) in searchResults"
          :key="row.id || i"
          class="result-card"
          @click="viewDetail(row)"
        >
          <div class="result-card-head">
            <el-tag size="small" :type="categoryType(row.category)" effect="plain">
              {{ categoryLabel(row.category) }}
            </el-tag>
            <div class="result-score">
              <div class="score-bar">
                <div class="score-fill" :style="{ width: Math.round((row.score || 0) * 100) + '%' }" />
              </div>
              <span class="score-num">{{ ((row.score || 0) * 100).toFixed(0) }}%</span>
            </div>
          </div>
          <h4 class="result-title">{{ row.title }}</h4>
          <p class="result-snippet">{{ row.snippet || row.content || '—' }}</p>
        </div>
        <el-empty v-if="!loading && searchResults.length === 0" description="未找到相关知识，试试其他关键词" />
      </div>

      <!-- 列表(全部知识, 表格视图) -->
      <div v-else class="list-wrap" v-loading="loading">
        <div
          v-for="row in list"
          :key="row.id"
          class="list-row"
          @click="viewDetail(row)"
        >
          <span class="list-id">{{ row.id }}</span>
          <span class="list-title">{{ row.title }}</span>
          <el-tag size="small" :type="categoryType(row.category)" effect="plain">
            {{ categoryLabel(row.category) }}
          </el-tag>
          <span class="list-tags">{{ row.tags || '—' }}</span>
          <span class="list-source">{{ row.source || '—' }}</span>
        </div>
        <el-empty v-if="!loading && list.length === 0" description="该分类下暂无知识" />
      </div>

      <!-- 分页:放在 list-wrap 外面,占整行,避免被 grid 挤压 -->
      <el-pagination
        v-if="!searchMode && pagination.total > 0"
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        class="pagination"
        @current-change="loadList"
        @size-change="loadList"
      />
    </section>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" :title="detail?.title || '知识详情'" width="720px">
      <div v-if="detail">
        <el-tag :type="categoryType(detail.category)" size="small">{{ categoryLabel(detail.category) }}</el-tag>
        <span v-if="detail.tags" class="detail-tags">标签: {{ detail.tags }}</span>
        <div class="markdown-body detail-content" v-html="renderMarkdown(detail.content)" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { marked } from 'marked'
import { knowledgeApi } from '@/api/knowledge'

const list = ref([])
const searchResults = ref([])
const loading = ref(false)
const searchText = ref('')
const filterCategory = ref('')
const searchMode = ref(false)
const showDetail = ref(false)
const detail = ref(null)
const inputFocused = ref(false)
const inputRef = ref(null)
const pagination = reactive({ page: 1, size: 20, total: 0 })

const totalPages = computed(() =>
  Math.max(1, Math.ceil(pagination.total / pagination.size))
)

const categories = [
  { label: '全部',   value: '' },
  { label: '疾病',   value: 'disease' },
  { label: '药品',   value: 'drug' },
  { label: '检查',   value: 'examination' },
  { label: '指南',   value: 'guideline' },
]

const hotKeywords = ['胸痛', '高血压', '糖尿病', '冠心病', '心律失常', '肺炎', '脑卒中']

const categoryLabel = (c) =>
  ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c || '未分类')
const categoryType = (c) =>
  ({ disease: 'danger', drug: 'warning', examination: 'success', guideline: 'info' }[c] || '')

marked.setOptions({ breaks: true, gfm: true })
const renderMarkdown = (text) => (text ? marked.parse(text) : '')

const totalCount = computed(() =>
  searchMode.value ? searchResults.value.length : pagination.total
)

const loadList = async () => {
  loading.value = true
  try {
    const res = await knowledgeApi.list({
      category: filterCategory.value || undefined,
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
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = async () => {
  const q = searchText.value.trim()
  if (!q) {
    searchMode.value = false
    return
  }
  loading.value = true
  try {
    // 后端 /search/query 返回 { query, results, total },取 results 数组
    const res = await knowledgeApi.search(q, 10)
    searchResults.value = res?.results || []
    searchMode.value = true
    // 滚到结果区(在小屏体验更好)
    nextTick(() => {
      document.querySelector('.result-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
  } catch (e) {
    ElMessage.error('检索失败')
  } finally {
    loading.value = false
  }
}

const quickSearch = async (kw) => {
  searchText.value = kw
  await handleSearch()
}

const setCategory = async (val) => {
  filterCategory.value = val
  pagination.page = 1
  // 如果当前在搜索模式,退出搜索再过滤
  if (searchMode.value) {
    searchMode.value = false
    searchText.value = ''
  }
  await loadList()
}

const exitSearch = async () => {
  searchMode.value = false
  searchText.value = ''
  await loadList()
}

const viewDetail = async (row) => {
  try {
    detail.value = await knowledgeApi.detail(row.id)
    showDetail.value = true
  } catch {
    ElMessage.error('加载详情失败')
  }
}

onMounted(() => {
  loadList()
  // 自动聚焦输入框(突出检索地位)
  nextTick(() => inputRef.value?.focus())
})
</script>

<style lang="scss" scoped>
@use '@/styles/tokens.scss' as t;

.kb-page {
  background: t.c('bg-soft');
  min-height: calc(100vh - 64px - 48px); // 减去导航和底部
}

/* ============================================
   上方 2/3 检索 Hero 区
   ============================================ */
.search-hero {
  position: relative;
  overflow: hidden;
  /* 上方 2/3:最小高度=视口 60vh,且自然延伸 */
  min-height: 60vh;
  padding: t.sp(16) t.sp(8) t.sp(12);
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg,
    t.c('bg-soft') 0%,
    t.c('primary-50') 60%,
    t.c('primary-100') 100%);
}

.search-deco {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  z-index: 0;
}
.search-deco-1 {
  top: -20%; right: -10%;
  width: 540px; height: 540px;
  background: radial-gradient(circle, rgba(79, 179, 169, 0.18) 0%, transparent 70%);
}
.search-deco-2 {
  bottom: -30%; left: -10%;
  width: 460px; height: 460px;
  background: radial-gradient(circle, rgba(232, 155, 108, 0.10) 0%, transparent 70%);
}

.search-inner {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 880px;
  margin: 0 auto;
  text-align: center;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: t.sp(2);
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid t.c('primary-100');
  border-radius: t.r('full');
  font-size: 13px;
  color: t.c('primary-700');
  margin-bottom: t.sp(5);
  box-shadow: t.shadow('xs');

  .pulse {
    width: 8px; height: 8px;
    background: t.c('success');
    border-radius: 50%;
    animation: pulse 2s infinite;
  }
}

.search-title {
  font-family: t.font("serif");
  font-size: 48px;
  font-weight: 700;
  line-height: 1.2;
  color: t.c('text-1');
  margin-bottom: t.sp(4);
  letter-spacing: -0.02em;

  .accent {
    background: linear-gradient(135deg, t.c('primary-600'), t.c('primary-500'));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
}

.search-subtitle {
  font-size: 16px;
  line-height: 1.7;
  color: t.c('text-2');
  margin-bottom: t.sp(8);
}

/* 大输入框 */
.search-bar {
  display: flex;
  align-items: center;
  gap: t.sp(3);
  padding: t.sp(3);
  background: t.c('surface');
  border-radius: t.r('xl');
  border: 2px solid transparent;
  box-shadow: t.shadow('md');
  transition: all t.dur("base") t.ease("out");
  margin-bottom: t.sp(5);

  &.active {
    border-color: t.c('primary-500');
    box-shadow: t.shadow('lg'), 0 0 0 4px rgba(79, 179, 169, 0.10);
  }
}

.search-bar-icon {
  font-size: 22px;
  color: t.c('text-3');
  margin: 0 t.sp(2);
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 18px;
  color: t.c('text-1');
  font-family: inherit;
  padding: t.sp(3) 0;

  &::placeholder {
    color: t.c('text-3');
  }
}

.search-btn {
  padding: t.sp(3) t.sp(8);
  font-size: 16px;
  border-radius: t.r('lg');

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
    transform: none;
  }
}

/* 分类 chips */
.category-chips {
  display: flex;
  justify-content: center;
  flex-wrap: wrap;
  gap: t.sp(2);
  margin-bottom: t.sp(5);
}

.chip {
  padding: t.sp(2) t.sp(4);
  border-radius: t.r('full');
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  border: 1px solid t.c('border');
  color: t.c('text-2');
  font-size: 13px;
  cursor: pointer;
  transition: all t.dur("base") t.ease("out");

  &:hover {
    border-color: t.c('primary-300');
    color: t.c('primary-600');
  }
  &.active {
    background: t.c('primary-500');
    color: #fff;
    border-color: t.c('primary-500');
  }
}

/* 推荐搜索 / 检索模式 */
.suggest-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: t.sp(2);
  justify-content: center;
  margin-top: t.sp(3);
}

.suggest-lbl {
  font-size: 13px;
  color: t.c('text-3');
  margin-right: t.sp(2);
}

.meta {
  font-size: 13px;
  color: t.c('text-2');
}

.symptom-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 14px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid t.c('border');
  border-radius: t.r('full');
  font-size: 13px;
  color: t.c('text-1');
  cursor: pointer;
  user-select: none;
  transition: all t.dur("base") t.ease("out");

  &:hover {
    background: t.c('primary-500');
    color: #fff;
    border-color: t.c('primary-500');
    transform: translateY(-1px);
  }
}

/* ============================================
   下方 1/3 结果区
   ============================================ */
.result-section {
  max-width: 1280px;
  margin: 0 auto;
  padding: t.sp(8) t.sp(8) t.sp(16);
}

.result-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: t.sp(5);
  padding-bottom: t.sp(4);
  border-bottom: 1px solid t.c('border');

  h3 {
    margin: 0;
    font-family: t.font("serif");
    font-size: 20px;
    font-weight: 600;
    color: t.c('text-1');
  }

  .result-count {
    font-size: 13px;
    color: t.c('text-3');
  }
}

/* 检索结果卡片视图 */
.search-result-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: t.sp(4);
}

.result-card {
  background: t.c('surface');
  border: 1px solid t.c('border');
  border-radius: t.r('lg');
  padding: t.sp(5);
  cursor: pointer;
  transition: all t.dur("base") t.ease("out");

  &:hover {
    transform: translateY(-3px);
    box-shadow: t.shadow('md');
    border-color: t.c('primary-300');
  }
}

.result-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: t.sp(3);
}

.result-score {
  display: flex;
  align-items: center;
  gap: t.sp(2);
  flex-shrink: 0;
}

.score-bar {
  width: 60px;
  height: 6px;
  background: t.c('bg');
  border-radius: t.r('full');
  overflow: hidden;
}

.score-fill {
  height: 100%;
  background: linear-gradient(90deg, t.c('primary-500'), t.c('primary-300'));
  border-radius: t.r('full');
  transition: width t.dur("slow") t.ease("out");
}

.score-num {
  font-size: 12px;
  color: t.c('primary-700');
  font-weight: 600;
  min-width: 32px;
  text-align: right;
}

.result-title {
  font-size: 16px;
  font-weight: 600;
  color: t.c('text-1');
  margin: 0 0 t.sp(2);
  line-height: 1.4;
}

.result-snippet {
  font-size: 13px;
  color: t.c('text-2');
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 列表视图 */
.list-wrap {
  background: t.c('surface');
  border: 1px solid t.c('border');
  border-radius: t.r('lg');
  overflow: hidden;
}

.list-row {
  display: grid;
  grid-template-columns: 60px 1.5fr 100px 1fr 1.2fr;
  gap: t.sp(4);
  align-items: center;
  padding: t.sp(4) t.sp(5);
  border-bottom: 1px solid t.c('border');
  cursor: pointer;
  transition: background t.dur("fast") t.ease("out");

  &:last-child { border-bottom: none; }
  &:hover { background: t.c('primary-50'); }

  .list-id {
    font-family: t.font("mono");
    color: t.c('text-3');
    font-size: 13px;
  }
  .list-title {
    font-weight: 500;
    color: t.c('text-1');
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .list-tags {
    font-size: 12px;
    color: t.c('text-3');
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .list-source {
    font-size: 12px;
    color: t.c('text-3');
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.pagination {
  /* 移到 .list-wrap 外面后,独占一行;不设 display flex,让 el-pagination 自带的
     display: flex 完整生效,避免与我们的 justify-content 冲突 */
  margin-top: t.sp(5);
  padding: 0 t.sp(2);   // 离开 result-section 的内边距,视觉上不再贴边
  width: 100%;
  display: flex;
  justify-content: flex-end;

  /* 小屏:让分页器内部允许换行,避免"显示不全" */
  :deep(.el-pagination) {
    flex-wrap: wrap;
    justify-content: flex-end;
    row-gap: 8px;
  }
  :deep(.el-pagination__sizes),
  :deep(.el-pagination__jump) {
    margin-left: 0;
  }
}

.detail-tags {
  margin-left: 8px;
  color: t.c('text-3');
  font-size: 13px;
}

.detail-content {
  margin-top: t.sp(3);
}

/* ============================================
   响应式
   ============================================ */
@media (max-width: 960px) {
  .search-title { font-size: 36px; }
  .search-subtitle { font-size: 14px; br { display: none; } }
  .search-bar { flex-wrap: wrap; }
  .search-btn { width: 100%; }
  .search-result-grid { grid-template-columns: 1fr; }
  .list-row {
    grid-template-columns: 1fr;
    gap: t.sp(2);
    .list-id { display: none; }
  }
}

@media (max-width: 640px) {
  .search-hero { padding: t.sp(10) t.sp(4) t.sp(8); min-height: 50vh; }
  .result-section { padding: t.sp(5) t.sp(4) t.sp(10); }
  .search-title { font-size: 28px; }
  .search-input { font-size: 16px; }
}
</style>
