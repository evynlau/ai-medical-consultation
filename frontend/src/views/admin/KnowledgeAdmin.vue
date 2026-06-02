<template>
  <div class="kb-admin">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <h3><el-icon><Reading /></el-icon> 知识库管理</h3>
          <div class="actions">
            <el-button type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon>
              新增知识
            </el-button>
            <el-button @click="reindex" :loading="reindexing">
              <el-icon><Refresh /></el-icon>
              重建索引
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" stripe>
        <el-table-column label="ID" prop="id" width="60" />
        <el-table-column label="标题" prop="title" min-width="200" show-overflow-tooltip />
        <el-table-column label="分类" prop="category" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="categoryType(row.category)">{{ categoryLabel(row.category) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="标签" prop="tags" show-overflow-tooltip />
        <el-table-column label="来源" prop="source" show-overflow-tooltip />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">查看</el-button>
            <el-button size="small" type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEdit" :title="editForm.id ? '编辑知识' : '新增知识'" width="700px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="editForm.title" />
        </el-form-item>
        <el-form-item label="分类" required>
          <el-select v-model="editForm.category" style="width: 200px">
            <el-option label="疾病" value="disease" />
            <el-option label="药品" value="drug" />
            <el-option label="检查" value="examination" />
            <el-option label="指南" value="guideline" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editForm.tags" placeholder="逗号分隔" />
        </el-form-item>
        <el-form-item label="来源">
          <el-input v-model="editForm.source" placeholder="可选" />
        </el-form-item>
        <el-form-item label="内容" required>
          <el-input v-model="editForm.content" type="textarea" :rows="12" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ editForm.id ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { adminApi } from '@/api/admin'
import { knowledgeApi } from '@/api/knowledge'

marked.setOptions({ breaks: true, gfm: true })

const list = ref([])
const loading = ref(false)
const categoryLabel = (c) => ({ disease: '疾病', drug: '药品', examination: '检查', guideline: '指南' }[c] || c)
const categoryType = (c) => ({ disease: 'danger', drug: 'warning', examination: 'success', guideline: 'info' }[c] || '')

const load = async () => {
  loading.value = true
  try {
    list.value = await knowledgeApi.list({ limit: 200 })
  } finally {
    loading.value = false
  }
}

const showEdit = ref(false)
const editForm = reactive({ id: null, title: '', category: 'disease', tags: '', source: '', content: '' })
const saving = ref(false)

const openCreate = () => {
  Object.assign(editForm, { id: null, title: '', category: 'disease', tags: '', source: '', content: '' })
  showEdit.value = true
}
const openEdit = (row) => {
  Object.assign(editForm, row)
  showEdit.value = true
}
const save = async () => {
  if (!editForm.title.trim() || !editForm.content.trim()) {
    ElMessage.warning('请填写标题和内容')
    return
  }
  saving.value = true
  try {
    if (editForm.id) {
      await adminApi.updateKnowledge(editForm.id, editForm)
      ElMessage.success('已更新')
    } else {
      await adminApi.createKnowledge(editForm)
      ElMessage.success('已创建,索引已重建')
    }
    showEdit.value = false
    load()
  } finally {
    saving.value = false
  }
}

const confirmDelete = async (row) => {
  await ElMessageBox.confirm(`确认删除「${row.title}」?`, '提示', { type: 'warning' })
  await adminApi.deleteKnowledge(row.id)
  ElMessage.success('已删除')
  load()
}

const reindexing = ref(false)
const reindex = async () => {
  reindexing.value = true
  try {
    const r = await adminApi.reindex()
    ElMessage.success(`索引已重建: ${r.count} 条`)
  } finally {
    reindexing.value = false
  }
}

const showDetail = ref(false)
const detail = ref(null)
const renderMarkdown = (t) => t ? marked.parse(t) : ''
const viewDetail = async (row) => {
  detail.value = await knowledgeApi.detail(row.id)
  showDetail.value = true
}

onMounted(load)
</script>

<style lang="scss" scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  h3 { margin: 0; display: flex; align-items: center; gap: 6px; }
  .actions { display: flex; gap: 8px; }
}
</style>
