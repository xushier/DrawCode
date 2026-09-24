<template>
  <div class="page records-page">
    <!-- 筛选栏 -->
    <div class="card toolbar">
      <div class="filters">
        <el-select v-model="q.user" placeholder="操作用户" clearable filterable size="default" class="f-item">
          <el-option v-for="u in users" :key="u" :label="u" :value="u" />
        </el-select>
        <el-select v-model="q.action" placeholder="操作类型" clearable size="default" class="f-item">
          <el-option v-for="(label, a) in ACTIONS" :key="a" :label="label" :value="a" />
        </el-select>
        <el-select v-model="q.table_id" placeholder="数据表" clearable size="default" class="f-item">
          <el-option v-for="t in tables" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-date-picker v-model="range" type="daterange" value-format="YYYY-MM-DD"
                        start-placeholder="开始日期" end-placeholder="结束日期"
                        class="f-item range" />
        <el-input v-model="q.search" placeholder="搜索内容…" clearable :prefix-icon="Search"
                  class="f-item search" @input="debouncedLoad" @clear="load" />
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <div>
        <el-button type="danger" plain :icon="Delete" @click="clearAll">清空记录</el-button>
      </div>
    </div>

    <!-- 时间线 -->
    <div class="card timeline-card" v-loading="loading">
      <el-empty v-if="!items.length && !loading" description="暂无操作记录" :image-size="72" />
      <el-scrollbar v-else max-height="calc(100vh - 210px)">
        <el-timeline class="tl">
          <el-timeline-item v-for="it in items" :key="it.id"
                            :timestamp="it.created_at" placement="top"
                            :color="tagColor(it.action)" :hollow="true">
            <div class="tl-card">
              <div class="tl-head">
                <el-tag size="small" :type="tagType(it.action)">{{ actionLabel(it.action) }}</el-tag>
                <span class="tl-user">
                  <el-icon><User /></el-icon>{{ it.user }}
                </span>
                <el-tag v-if="it.table_name" size="small" type="info" effect="plain">{{ it.table_name }}</el-tag>
                <span v-if="it.target" class="tl-target">{{ it.target }}</span>
              </div>
              <div v-if="detailOf(it)" class="tl-detail">
                <template v-if="it.action === 'record_update'">
                  <div v-for="(val, label) in detailOf(it).changes" :key="label" class="tl-change">
                    <b>{{ label }}</b><span class="old">{{ fmt(val[0]) }}</span>
                    <el-icon><Right /></el-icon>
                    <span class="new">{{ fmt(val[1]) }}</span>
                  </div>
                </template>
                <template v-else-if="it.action === 'record_add'">
                  <span v-for="(v, k) in compactData(it)" :key="k" class="tl-kv">{{ k }}：{{ v }}</span>
                </template>
                <template v-else-if="it.action === 'record_delete'">
                  <span v-for="(v, k) in compactData(it)" :key="k" class="tl-kv">{{ k }}：{{ v }}</span>
                </template>
                <template v-else-if="typeof detailOf(it) === 'object'">
                  <span class="tl-kv">{{ JSON.stringify(detailOf(it)) }}</span>
                </template>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </el-scrollbar>
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                       layout="total, prev, pager, next" background
                       @update:current-page="load" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'
import { http } from '@/api'

const ACTIONS = {
  login: '登录', logout: '退出', password_change: '修改密码', avatar_change: '更换头像',
  record_add: '新增数据', record_update: '修改数据', record_delete: '删除数据',
  import: '导入数据', export: '导出数据',
  table_create: '新建数据表', table_rename: '重命名数据表', table_delete: '删除数据表',
  field_add: '新增字段', field_update: '修改字段', field_delete: '删除字段',
  settings_update: '修改设置', ops_clear: '清空操作记录', logs_clear: '清空系统日志'
}

const q = reactive({ user: '', action: '', table_id: null, search: '' })
const range = ref(null)
const users = ref([])
const tables = ref([])
const items = ref([])
const total = ref(0)
const page = ref(1)
const size = 20
const loading = ref(false)

const TAG_TYPES = {
  record_add: 'success', record_update: 'warning', record_delete: 'danger',
  import: 'success', export: 'primary', login: 'info', logout: 'info'
}

function actionLabel(a) { return ACTIONS[a] || a }
function tagType(a) { return TAG_TYPES[a] || 'info' }
function tagColor(a) {
  const map = {
    record_add: '#2f9e6e', record_delete: '#d05650', record_update: '#d07e2d',
    import: '#50c2a0', export: '#3a7bd5', login: '#8b95a1', logout: '#8b95a1'
  }
  return map[a] || '#8b95a1'
}

function detailOf(it) {
  if (!it.detail) return null
  try { return JSON.parse(it.detail) } catch { return it.detail }
}

function compactData(it) {
  const d = detailOf(it)
  const data = d?.data || {}
  const out = {}
  for (const k of ['drawing_no', 'name', 'model', 'project', 'applicant', 'remark']) {
    if (data[k]) out[k] = Array.isArray(data[k]) ? data[k].join('、') : data[k]
  }
  return out
}

function fmt(v) {
  if (Array.isArray(v)) return v.join('、') || '空'
  return String(v ?? '空') || '空'
}

async function load() {
  loading.value = true
  try {
    const params = {
      page: page.value, page_size: size,
      search: q.search, user: q.user, action: q.action,
      table_id: q.table_id || ''
    }
    if (range.value?.length === 2) {
      params.start = range.value[0]
      params.end = range.value[1]
    }
    const res = await http.get('/ops', { params })
    items.value = res.items
    total.value = res.total
    users.value = res.users
  } finally {
    loading.value = false
  }
}

let t = null
function debouncedLoad() {
  clearTimeout(t)
  t = setTimeout(load, 300)
}

function reset() {
  q.user = q.action = q.search = ''
  q.table_id = null
  range.value = null
  page.value = 1
  load()
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空全部操作记录吗？此操作不可恢复。', '清空确认',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' })
  } catch { return }
  await http.delete('/ops')
  ElMessage.success('操作记录已清空')
  load()
}

onMounted(async () => {
  load()
  try {
    const res = await http.get('/tables')
    tables.value = res.tables
  } catch { /* ignore */ }
})
</script>

<style scoped>
.records-page { height: 100%; overflow: hidden; }
.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; padding: 10px 12px; flex: none; flex-wrap: wrap;
}
.filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.f-item { width: 150px; }
.f-item.range { width: 240px; }
.f-item.search { width: 200px; }

.timeline-card { flex: 1; min-height: 0; padding: 16px 18px; overflow: hidden; display: flex; flex-direction: column; }
.tl { padding: 4px 6px 0 4px; }
.tl-card { padding-bottom: 2px; }
.tl-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tl-user { display: inline-flex; align-items: center; gap: 3px; font-size: 13px; color: var(--dc-text); }
.tl-target { font-weight: 600; color: var(--dc-primary); font-size: 13px; }
.tl-detail { margin-top: 7px; display: flex; flex-wrap: wrap; gap: 6px 14px; }
.tl-kv { font-size: 12.5px; color: var(--dc-text-soft); }
.tl-change { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; }
.tl-change b { color: var(--dc-text); font-weight: 600; }
.tl-change .old { color: #c9506e; text-decoration: line-through; }
.tl-change .new { color: #2f9e6e; font-weight: 500; }
.pager { display: flex; justify-content: flex-end; padding-top: 10px; flex: none; }

@media (max-width: 768px) {
  .records-page { overflow-y: auto; }
  .f-item, .f-item.range, .f-item.search { width: 100%; }
}
</style>
