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
                  class="f-item search" @input="debouncedLoad" @clear="reload" />
        <el-button type="primary" :icon="Search" @click="reload">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </div>
      <div class="toolbar-right">
        <el-segmented v-model="mode" :options="modeOptions" size="default" @change="reload" />
        <el-button type="danger" plain :icon="Delete" @click="clearAll">清空记录</el-button>
      </div>
    </div>

    <!-- 记录表格 -->
    <div class="card table-card" v-loading="loading">
      <el-table :data="items" stripe size="small" class="dc-table" height="100%">
        <template #empty><el-empty description="暂无操作记录" :image-size="72" /></template>
        <el-table-column type="expand" width="36">
          <template #default="{ row }">
            <div class="detail-wrap">
              <template v-if="row.action === 'record_update' && detailOf(row)?.changes">
                <div v-for="(val, label) in detailOf(row).changes" :key="label" class="detail-change">
                  <b>{{ label }}</b>
                  <span class="old">{{ fmt(val[0]) }}</span>
                  <el-icon><Right /></el-icon>
                  <span class="new">{{ fmt(val[1]) }}</span>
                </div>
              </template>
              <template v-else-if="row.action === 'record_add' || row.action === 'record_delete'">
                <span v-for="(v, k) in compactData(row)" :key="k" class="detail-kv">{{ k }}：{{ v }}</span>
              </template>
              <template v-else-if="detailOf(row) && typeof detailOf(row) === 'object'">
                <span v-for="(v, k) in detailOf(row)" :key="k" class="detail-kv">
                  {{ detailLabel(k) }}：{{ detailVal(v) }}
                </span>
              </template>
              <span v-else class="muted">无详细数据</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column prop="user" label="操作人" width="100" show-overflow-tooltip />
        <el-table-column label="操作" width="96" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="tagType(row.action)">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="table_name" label="数据表" width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.table_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="对象" min-width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.target" class="row-target">{{ row.target }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="明细" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="summaryOf(row)" class="row-summary">{{ summaryOf(row) }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div v-if="mode === 'page'" class="card pagination-card">
      <el-pagination v-model:current-page="page" :page-size="size" :total="total"
                     layout="total, prev, pager, next" background
                     @update:current-page="load(false)" />
    </div>
    <!-- 懒加载模式提示 -->
    <div v-else-if="items.length" class="load-hint muted">
      {{ hasMore ? '下拉加载更多…' : `已全部加载（${items.length} 条）` }}
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, Right } from '@element-plus/icons-vue'
import { http } from '@/api'

const ACTIONS = {
  login: '登录', logout: '退出', register: '注册', password_change: '修改密码', avatar_change: '更换头像',
  record_add: '新增数据', record_update: '修改数据', record_delete: '删除数据',
  import: '导入数据', export: '导出数据',
  table_create: '新建数据表', table_rename: '重命名数据表', table_delete: '删除数据表',
  field_add: '新增字段', field_update: '修改字段', field_delete: '删除字段',
  settings_update: '修改设置', ops_clear: '清空操作记录', logs_clear: '清空系统日志',
  backup: '数据备份', backup_delete: '删除备份', backup_restore: '恢复备份',
  user_create: '新建用户', user_update: '用户管理', user_delete: '删除用户'
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
const loadingMore = ref(false)

/* 展示模式：懒加载 / 分页，本地记忆 */
const mode = ref(localStorage.getItem('dc-ops-mode') || 'lazy')
const modeOptions = [
  { label: '懒加载', value: 'lazy' },
  { label: '分页', value: 'page' }
]
watch(mode, v => localStorage.setItem('dc-ops-mode', v))
const LAZY_SIZE = 50
const hasMore = computed(() => items.value.length < total.value)

const TAG_TYPES = {
  record_add: 'success', record_update: 'warning', record_delete: 'danger',
  import: 'success', export: 'primary', login: 'info', logout: 'info',
  backup: 'primary', backup_restore: 'warning', backup_delete: 'danger'
}

function actionLabel(a) { return ACTIONS[a] || a }
function tagType(a) { return TAG_TYPES[a] || 'info' }

function detailOf(it) {
  if (!it.detail) return null
  try { return JSON.parse(it.detail) } catch { return it.detail }
}

/* detail 键名中文映射（操作记录友好展示） */
const DETAIL_LABELS = {
  keys: '修改项', added: '成功', failed: '失败', count: '数量', file: '文件',
  old_name: '原表名', new_name: '新表名', label: '字段名', type: '类型',
  id: 'ID', name: '名称', required: '必填', default_value: '默认值',
  options: '可选值', user: '用户', table: '数据表', target: '对象'
}
function detailLabel(k) { return DETAIL_LABELS[k] || k }

function detailVal(v) {
  if (v === null || v === undefined) return '空'
  if (Array.isArray(v)) return v.map(x => (x && typeof x === 'object' ? JSON.stringify(x) : x)).join('、') || '空'
  if (typeof v === 'boolean') return v ? '是' : '否'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

/* record_add / record_delete 的 data 摘要：中文键名 */
const DATA_LABELS = {
  drawing_no: '图号', name: '名称', model: '型号', project: '工程/项目',
  applicant: '申请人', remark: '备注'
}
function compactData(it) {
  const d = detailOf(it)
  const data = d?.data || {}
  const out = {}
  for (const k of ['drawing_no', 'name', 'model', 'project', 'applicant', 'remark']) {
    if (data[k]) out[DATA_LABELS[k] || k] = Array.isArray(data[k]) ? data[k].join('、') : data[k]
  }
  return out
}

function fmt(v) {
  if (Array.isArray(v)) return v.join('、') || '空'
  return String(v ?? '空') || '空'
}

/* 明细列单行摘要：修改展示「字段：旧 → 新」，新增/删除展示关键字段，其余展示键值 */
function summaryOf(row) {
  const d = detailOf(row)
  if (!d) return ''
  if (row.action === 'record_update' && d?.changes) {
    return Object.entries(d.changes)
      .map(([k, v]) => `${k}：${fmt(v[0])} → ${fmt(v[1])}`).join('；')
  }
  if (row.action === 'record_add' || row.action === 'record_delete') {
    return Object.entries(compactData(row)).map(([k, v]) => `${k}：${v}`).join('；')
  }
  if (typeof d === 'object') {
    return Object.entries(d)
      .map(([k, v]) => `${detailLabel(k)}：${detailVal(v)}`).join('；')
  }
  return String(d)
}

async function load(append = false) {
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const params = {
      page: page.value,
      page_size: mode.value === 'page' ? size : LAZY_SIZE,
      search: q.search, user: q.user, action: q.action,
      table_id: q.table_id || ''
    }
    if (range.value?.length === 2) {
      params.start = range.value[0]
      params.end = range.value[1]
    }
    const res = await http.get('/ops', { params })
    if (append) items.value.push(...res.items)
    else items.value = res.items
    total.value = res.total
    users.value = res.users
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function reload() {
  page.value = 1
  load(false)
}

/* 懒加载：表格滚动触底自动追加 */
let scrollEl = null
let scrollTimer = null
function onBodyScroll() {
  if (mode.value !== 'lazy' || !hasMore.value || loadingMore.value || loading.value) return
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => {
    if (!scrollEl) return
    if (scrollEl.scrollTop + scrollEl.clientHeight >= scrollEl.scrollHeight - 60) {
      page.value++
      load(true)
    }
  }, 80)
}

let t = null
function debouncedLoad() {
  clearTimeout(t)
  t = setTimeout(reload, 300)
}

function reset() {
  q.user = q.action = q.search = ''
  q.table_id = null
  range.value = null
  reload()
}

async function clearAll() {
  try {
    await ElMessageBox.confirm('确定清空全部操作记录吗？此操作不可恢复。', '清空确认',
      { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' })
  } catch { return }
  await http.delete('/ops')
  ElMessage.success('操作记录已清空')
  reload()
}

onMounted(async () => {
  reload()
  try {
    const res = await http.get('/tables')
    tables.value = res.tables
  } catch { /* ignore */ }
  /* 在 el-table 渲染后挂载滚动监听 */
  setTimeout(() => {
    scrollEl = document.querySelector('.records-page .table-card .el-scrollbar__wrap') ||
              document.querySelector('.records-page .table-card .el-table__body-wrapper')
    scrollEl?.addEventListener('scroll', onBodyScroll, { passive: true })
  }, 500)
})

onBeforeUnmount(() => scrollEl?.removeEventListener('scroll', onBodyScroll))
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

.table-card { flex: 1; min-height: 0; padding: 0; overflow: hidden; }
.pagination-card { padding: 8px 12px; flex: none; display: flex; justify-content: flex-end; }
.load-hint { text-align: center; font-size: 12px; padding: 6px 0 2px; flex: none; }
.toolbar-right { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }

.row-target { font-weight: 600; color: var(--dc-primary); font-size: 13px; }
.row-summary { color: var(--dc-text-soft); font-size: 12.5px; }
.detail-wrap {
  padding: 2px 12px 10px;
  display: flex; flex-wrap: wrap; gap: 8px 20px;
}
.detail-kv { font-size: 12.5px; color: var(--dc-text-soft); }
.detail-change { display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; }
.detail-change b { color: var(--dc-text); font-weight: 600; }
.detail-change .old { color: #c9506e; text-decoration: line-through; }
.detail-change .new { color: #2f9e6e; font-weight: 500; }

@media (max-width: 768px) {
  .records-page { overflow-y: auto; }
  .filters { width: 100%; }
  .f-item, .f-item.range, .f-item.search { width: 100%; min-width: 0; }
  .toolbar-right { width: 100%; justify-content: space-between; }
}
</style>
