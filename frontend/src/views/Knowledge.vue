<template>
  <div class="kb page-container">
    <el-card shadow="never">
      <template #header>
        <div class="header-row">
          <h3><el-icon><Reading /></el-icon> 医学知识库</h3>
          <div class="actions">
            <el-input
              v-model="searchText"
              placeholder="搜索症状、疾病、药品…"
              clearable
              style="width: 280px"
              @keydown.enter="handleSearch"
            >
              <template #append>
                <el-button :icon="Search" @click="handleSearch" />
              </template>
            </el-input>
            <el-select v-model="filterCategory" placeholder="全部分类" clearable style="width: 140px" @change="loadList">
              <el-option label="疾病" value="disease" />
              <el-option label="药品" value="drug" />
              <el-option label="检查" value="examination" />
              <el-option label="指南" value="guideline" />
            </el-select>
          </div>
        </div>
      </template>

      <!-- 检索结果(检索时显示) -->
      <template v-if="searchMode">
        <div class="search-info">
          关键词 "<b>{{ searchText }}</b>" 的语义检索结果 ({{ searchResults.length }} 条)
          <el-button text type="primary" @click="exitSearch">返回列表</el-button>
        </div>
        <el-table :data="searchResults" @row-click="viewDetail" stripe>
          <el-table-column label="标题" prop="title" />
          <el-table-column label="分类" prop="category" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="categoryType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="相关度" width="120">
            <template #default="{ row }">
              <el-progress :percentage="Math.round(row.score * 100)" :stroke-width="8" />
            </template>
          </el-table-column>
          <el-table-column label="内容预览" prop="snippet" show-overflow-tooltip />
        </el-table>
      </template>

      <!-- 列表模式 -->
      <template v-else>
        <el-table :data="list" v-loading="loading" stripe @row-click="viewDetail">
          <el-table-column label="ID" prop="id" width="60" />
          <el-table-column label="标题" prop="title" />
          <el-table-column label="分类" width="120">
            <template #default="{ row }">
              <el-tag size="small" :type="categoryType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="标签" prop="tags" show-overflow-tooltip />
          <el-table-column label="来源" prop="source" show-overflow-tooltip />
        </el-table>

        <!-- 分页 -->
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          class="pagination"
          @current-change="loadList"
          @size-change="loadList"
        />
      </template>
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="showDetail" :title="detail?.title || '知识详情'" width="700px">
      <div v-if="detail">
        <el-tag :type="categoryType(detail.category)" size="small">{{ categoryLabel(detail.category) }}</el-tag>
        <span v-if="detail.tags" style="margin-left: 8px; color: #909399; font-size: 13px">标签: {{ detail.tags }}</span>
        <div class="markdown-body" style="margin-top: 12px" v-html="renderMarkdown(detail.content)"></div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted } from 'vue'
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
const pagination = reactive({ page: 1, size: 20, total: 0 })

marked.setOptions({ breaks: true, gfm: true })
const renderMarkdown = (text) => text ? marked.parse(text) : ''

const categoryLabel = (c) => ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c)
const categoryType = (c) => ({ disease: 'danger', drug: 'warning', examination: 'success', guideline: 'info' }[c] || '')

const loadList = async () => {
  loading.value = true
  try {
    // 后端 /api/v1/knowledge 一次返回当前页(最多 500 条);翻页用 offset+limit
    const res = await knowledgeApi.list({
      category: filterCategory.value || undefined,
      keyword: searchText.value || undefined,
      limit: pagination.size,
      offset: (pagination.page - 1) * pagination.size
    })
    list.value = res
    // 估算 total:如果返回少于 size 表明已到末页,否则可能还有
    if (res.length < pagination.size) {
      pagination.total = (pagination.page - 1) * pagination.size + res.length
    } else {
      // 还有下一页,粗略按 page*size 估算(下次可拉下一页验证)
      pagination.total = pagination.page * pagination.size + 1
    }
    // 第一次加载或过滤变化时,若返回满页,主动多查一次估算
  } catch (e) {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

// 分类或关键词变化时回到第一页
watch([filterCategory, searchText], () => {
  pagination.page = 1
  if (!searchMode.value) loadList()
})

const handleSearch = async () => {
  if (!searchText.value.trim()) {
    searchMode.value = false
    return
  }
  loading.value = true
  try {
    searchResults.value = await knowledgeApi.search(searchText.value.trim(), 10)
    searchMode.value = true
  } catch (e) {
    ElMessage.error('检索失败')
  } finally {
    loading.value = false
  }
}

const exitSearch = () => {
  searchMode.value = false
  searchText.value = ''
  loadList()
}

const viewDetail = async (row) => {
  try {
    detail.value = await knowledgeApi.detail(row.id)
    showDetail.value = true
  } catch {
    ElMessage.error('加载详情失败')
  }
}

onMounted(loadList)
</script>

<style lang="scss" scoped>
.header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
  .actions { display: flex; gap: 8px; }
}
.search-info { margin-bottom: 12px; color: #606266; }
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
  display: flex;
}
:deep(.el-table__row) { cursor: pointer; }
</style>
