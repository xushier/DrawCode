<template>
  <div class="page data-page">
    <!-- 表切换 -->
    <el-tabs v-model="activeId" @tab-change="onTableChange" class="dc-tabs page-tabs">
      <el-tab-pane v-for="t in tables" :key="t.id" :name="t.id">
        <template #label>
          <span class="tab-label">
            <el-icon><Tickets /></el-icon>
            {{ t.name }}
            <span class="tab-count tabular">{{ t.count }}</span>
          </span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- 工具栏 -->
    <div class="card toolbar">
      <div class="toolbar-left">
        <el-button v-if="store.canAdd" type="primary" :icon="Plus" @click="openCreate">申请图号</el-button>
        <el-button v-if="store.isAdmin && selMode !== 'none' && selectedRows.length"
                   type="danger" plain :icon="Delete" @click="onBatchDelete">
          删除选中（{{ selectedRows.length }}）
        </el-button>
        <el-button v-if="store.isAdmin" :icon="Upload" @click="importVisible = true">导入</el-button>
        <el-button :icon="Download" :loading="exporting" @click="doExport">导出</el-button>
      </div>
      <div class="toolbar-right">
        <el-input v-model="search" placeholder="搜索全表内容…" :prefix-icon="Search"
                  clearable class="search-input" @input="onSearchDebounced" @clear="reload" />
        <el-popover :width="340" trigger="click" persistent>
          <template #reference>
            <el-badge :value="filterCount" :hidden="!filterCount" :offset="[-2, 6]">
              <el-button :icon="Filter">筛选</el-button>
            </el-badge>
          </template>
          <FilterPanel :key="activeId" ref="filterRef" v-model="filters"
                       :fields="fields" :options="options" @update:model-value="reload" />
        </el-popover>
        <el-popover :width="260" trigger="click">
          <template #reference>
            <el-button :icon="Menu">列设置</el-button>
          </template>
          <div class="cols-pop">
            <div class="cols-head">
              <span class="muted">显示列</span>
              <el-button link type="primary" size="small" @click="allColumns(true)">全选</el-button>
            </div>
            <el-checkbox-group v-model="visibleKeys">
              <el-checkbox v-for="f in fields" :key="f.key" :value="f.key" :label="f.key">
                {{ f.label }}
              </el-checkbox>
            </el-checkbox-group>
            <div class="pop-sec muted">表格外观</div>
            <div class="pop-row">
              <span>选择行</span>
              <el-segmented v-model="selMode" :options="selOptions" size="small" />
            </div>
          </div>
        </el-popover>
        <el-segmented v-model="mode" :options="modeOptions" size="default"
                      @change="reload" class="mode-seg" />
        <span class="muted total-hint tabular">共 {{ total }} 条</span>
      </div>
    </div>

    <!-- 数据表 -->
    <div class="card table-card" v-loading="loading">
      <el-table ref="tableRef" :data="records" stripe size="small"
                class="dc-table"
                height="100%" :row-key="r => r.id"
                :highlight-current-row="selMode === 'single'"
                :default-sort="{ prop: 'data.sn', order: 'descending' }"
                @sort-change="onSortChange" @row-click="onRowClick"
                @selection-change="onSelectionChange" v-el-scroll>
        <template #empty>
          <el-empty :description="search || filterCount ? '未找到匹配数据'
            : (store.canAdd ? '暂无数据，点击「申请图号」新增' : '暂无数据')"
                    :image-size="72" />
        </template>
        <el-table-column v-if="selMode === 'multi'" type="selection" width="42" />
        <el-table-column v-if="selMode === 'single'" label="" width="42" align="center">
          <template #default="{ row }">
            <el-radio :model-value="selSingleId" :value="row.id"
                      @update:model-value="v => (selSingleId = v)" />
          </template>
        </el-table-column>
        <el-table-column v-for="f in visibleFields" :key="f.key" :prop="'data.' + f.key"
                         :label="f.label" sortable="custom"
                         :align="f.key === 'sn' ? 'center' : 'left'"
                         :width="f.key === 'sn' ? 72 : undefined"
                         :min-width="colWidth(f)" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="f.key === 'sn'" class="tabular">{{ row.data.sn }}</span>
            <template v-else-if="Array.isArray(row.data[f.key])">
              <el-tag v-for="v in row.data[f.key]" :key="v" size="small" effect="plain"
                      style="margin-right: 4px">{{ v }}</el-tag>
            </template>
            <el-tag v-else-if="f.type === 'switch'" size="small" :type="row.data[f.key] ? 'success' : 'info'">
              {{ row.data[f.key] ? '开' : '关' }}
            </el-tag>
            <span v-else>{{ fmtCell(row.data[f.key]) }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="store.authed" label="操作" width="132" fixed="right" align="center">
          <template #default="{ row }">
            <template v-if="store.isAdmin || row.created_by === store.user?.username">
              <div class="op-btns">
                <el-button size="small" type="primary" text bg @click="openEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" text bg @click="onDelete(row)">删除</el-button>
              </div>
            </template>
            <span v-else class="muted" style="font-size: 12px">—</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页模式 -->
    <div v-if="mode === 'page'" class="card pagination-card">
      <el-pagination v-model:current-page="page" :page-size="pageSize" :total="total"
                     :page-sizes="[50, 100, 200]" layout="total, sizes, prev, pager, next, jumper"
                     @update:current-page="load(false)" @update:page-size="onPageSize" />
    </div>
    <!-- 懒加载模式提示 -->
    <div v-else-if="records.length" class="load-hint muted">
      {{ hasMore ? '下拉加载更多…' : `已全部加载（${records.length} 条）` }}
    </div>

    <!-- 申请 / 编辑 -->
    <RecordDialog v-model="recordVisible" :table="activeTable" :record="editing"
                  :options="options" @saved="onSaved" />

    <!-- 导入 -->
    <el-dialog v-model="importVisible" title="导入 Excel（附加模式，不覆盖现有数据）"
               width="520px" append-to-body destroy-on-close>
      <template v-if="!importResult">
        <el-upload drag :auto-upload="false" :limit="1" accept=".xlsx,.xls"
                   :on-change="f => (importFile = f.raw)" :on-remove="() => (importFile = null)"
                   class="import-upload">
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖入或 <em>点击选择</em> Excel 文件</div>
          <template #tip>
            <div class="el-upload__tip muted">
              第一行需为列标题，需与字段名一致；
              <el-link type="primary" :underline="false" style="font-size:12px;vertical-align:baseline"
                       @click="downloadTemplate">下载导入模板</el-link>
            </div>
          </template>
        </el-upload>
      </template>
      <template v-else>
        <el-result :icon="importResult.failed.length ? 'warning' : 'success'"
                   :title="`成功导入 ${importResult.added} 条${importResult.failed.length ? '，失败 ' + importResult.failed.length + ' 条' : ''}`">
          <template #extra>
            <div v-if="importResult.ignored_columns?.length" class="muted" style="margin-bottom: 6px">
              忽略的列：{{ importResult.ignored_columns.join('、') }}
            </div>
            <el-scrollbar v-if="importResult.failed.length" max-height="220px" class="import-fails">
              <div v-for="f in importResult.failed" :key="f.row" class="fail-row">
                第 {{ f.row }} 行：{{ f.reason }}
              </div>
            </el-scrollbar>
          </template>
        </el-result>
      </template>
      <template #footer>
        <template v-if="!importResult">
          <el-button @click="importVisible = false">取 消</el-button>
          <el-button type="primary" :disabled="!importFile" :loading="importing" @click="doImport">开始导入</el-button>
        </template>
        <template v-else>
          <el-button @click="importResult = null">继续导入</el-button>
          <el-button type="primary" @click="importVisible = false">完 成</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Upload, Download, Search, Filter, Menu, Delete } from '@element-plus/icons-vue'
import { http, downloadBlob } from '@/api'
import { useApp } from '@/store'
import RecordDialog from '@/components/RecordDialog.vue'
import FilterPanel from '@/components/FilterPanel.vue'

const store = useApp()

const tables = ref([])
const activeId = ref(null)
const fields = ref([])
const records = ref([])
const total = ref(0)
const hasMore = ref(false)
const page = ref(1)
const pageSize = ref(100)
const mode = ref(localStorage.getItem('dc-view-mode') || 'lazy')
const modeOptions = [
  { label: '懒加载', value: 'lazy' },
  { label: '分页', value: 'page' }
]
const search = ref('')
const filters = ref({})
const sortKey = ref('sn')
const sortOrder = ref('desc')
const loading = ref(false)
const loadingMore = ref(false)
const exporting = ref(false)
const visibleKeys = ref([])
const options = reactive({})
const tableRef = ref()
const filterRef = ref()

/* 表格外观：选择行（无 / 单选 / 多选），本地记忆 */
const selMode = ref(localStorage.getItem('dc-selmode') || 'none')
const selOptions = [
  { label: '无', value: 'none' },
  { label: '单选', value: 'single' },
  { label: '多选', value: 'multi' }
]
const selection = ref([])
const selSingleId = ref(null)
watch(selMode, v => {
  localStorage.setItem('dc-selmode', v)
  selection.value = []
  selSingleId.value = null
})
const selectedRows = computed(() =>
  selMode.value === 'multi' ? selection.value
    : selSingleId.value ? [records.value.find(r => r.id === selSingleId.value)].filter(Boolean)
    : [])

function onSelectionChange(rows) { selection.value = rows }
function onRowClick(row) { if (selMode.value === 'single') selSingleId.value = row.id }

const activeTable = computed(() => tables.value.find(t => t.id === activeId.value) || null)
const filterCount = computed(() => Object.keys(filters.value).length)
const visibleFields = computed(() => fields.value.filter(f => visibleKeys.value.includes(f.key)))

/* ---------------- 数据加载 ---------------- */

async function loadTables() {
  const res = await http.get('/tables')
  tables.value = res.tables
  if (!tables.value.length) return
  let saved = parseInt(localStorage.getItem('dc-active-table'))
  if (!tables.value.some(t => t.id === saved)) saved = tables.value[0].id
  activeId.value = saved
  await onTableChange()
}

async function onTableChange() {
  localStorage.setItem('dc-active-table', activeId.value)
  const t = activeTable.value
  fields.value = t ? t.fields : []
  initVisibleKeys()
  await loadOptions()
  reload()
}

async function loadOptions() {
  if (!activeId.value) return
  try {
    const res = await http.get(`/tables/${activeId.value}/options`)
    Object.keys(options).forEach(k => delete options[k])
    Object.assign(options, res.options)
  } catch { /* 静默 */ }
}

function initVisibleKeys() {
  const key = `dc-cols-${activeId.value}`
  const saved = localStorage.getItem(key)
  if (saved) {
    try {
      const list = JSON.parse(saved)
      const valid = fields.value.filter(f => list.includes(f.key)).map(f => f.key)
      const missing = fields.value.filter(f => !list.includes(f.key))
        .filter(f => f.is_system).map(f => f.key)
      visibleKeys.value = [...valid, ...missing]
    } catch { visibleKeys.value = fields.value.map(f => f.key) }
  } else {
    visibleKeys.value = fields.value.map(f => f.key)
  }
}

watch(visibleKeys, () => {
  if (activeId.value) localStorage.setItem(`dc-cols-${activeId.value}`, JSON.stringify(visibleKeys.value))
}, { deep: true })

function allColumns(all) {
  visibleKeys.value = all ? fields.value.map(f => f.key) : []
}

async function load(append = false) {
  if (!activeId.value) return
  if (append) loadingMore.value = true
  else loading.value = true
  try {
    const params = {
      search: search.value,
      filters: JSON.stringify(filters.value),
      sort: sortKey.value,
      order: sortOrder.value,
      page: page.value,
      page_size: mode.value === 'page' ? pageSize.value : 50,
      mode: mode.value
    }
    const res = await http.get(`/tables/${activeId.value}/records`, { params })
    total.value = res.total
    hasMore.value = res.has_more
    if (append) records.value.push(...res.items)
    else records.value = res.items
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function reload() {
  page.value = 1
  load(false)
}

/* ---------------- 搜索 / 排序 / 懒加载 ---------------- */

let searchTimer = null
function onSearchDebounced() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 300)
}

function onSortChange({ prop, order }) {
  if (order) {
    sortKey.value = (prop || '').replace('data.', '')
    sortOrder.value = order === 'ascending' ? 'asc' : 'desc'
  } else {
    sortKey.value = 'sn'
    sortOrder.value = 'desc'
  }
  reload()
}

let scrollEl = null
let scrollTimer = null
function onBodyScroll() {
  if (mode.value !== 'lazy' || !hasMore.value || loadingMore.value || loading.value) return
  clearTimeout(scrollTimer)
  scrollTimer = setTimeout(() => {
    const el = document.querySelector('.table-card .el-scrollbar__wrap') ||
               document.querySelector('.table-card .el-table__body-wrapper')
    if (!el) return
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 60) {
      page.value++
      load(true)
    }
  }, 80)
}

const vElScroll = {
  mounted() {
    /* 在 el-table 渲染后挂载滚动监听 */
    setTimeout(() => {
      scrollEl = document.querySelector('.table-card .el-scrollbar__wrap') ||
                document.querySelector('.table-card .el-table__body-wrapper')
      scrollEl?.addEventListener('scroll', onBodyScroll, { passive: true })
    }, 500)
  },
  unmounted() {
    scrollEl?.removeEventListener('scroll', onBodyScroll)
  }
}

onMounted(loadTables)
onBeforeUnmount(() => scrollEl?.removeEventListener('scroll', onBodyScroll))

/* ---------------- 新增 / 编辑 / 删除 ---------------- */

const recordVisible = ref(false)
const editing = ref(null)

function openCreate() {
  editing.value = null
  recordVisible.value = true
}
function openEdit(row) {
  editing.value = row
  recordVisible.value = true
}

async function onSaved() {
  await loadOptions()
  reload()
  const t = activeTable.value
  if (t) t.count = (t.count || 0) + 1
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除该记录吗？图号「${row.data.drawing_no || row.data.name || ''}」将被移除。`,
      '删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.delete(`/records/${row.id}`)
  ElMessage.success('记录已删除')
  reload()
  const t = activeTable.value
  if (t) t.count = Math.max(0, (t.count || 1) - 1)
  await loadOptions()
}

async function onBatchDelete() {
  const rows = selectedRows.value
  if (!rows.length) return
  try {
    await ElMessageBox.confirm(
      `确定删除选中的 ${rows.length} 条记录吗？删除后不可恢复。`,
      '批量删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  for (const r of rows) await http.delete(`/records/${r.id}`)
  ElMessage.success(`已删除 ${rows.length} 条记录`)
  selection.value = []
  selSingleId.value = null
  reload()
  const t = activeTable.value
  if (t) t.count = Math.max(0, (t.count || 0) - rows.length)
  await loadOptions()
}

/* ---------------- 导入 / 导出 ---------------- */

const importVisible = ref(false)
const importFile = ref(null)
const importing = ref(false)
const importResult = ref(null)

async function doImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await http.post(`/tables/${activeId.value}/import`, fd)
    importResult.value = res
    await loadOptions()
    await loadTablesRefreshCount()
  } finally {
    importing.value = false
  }
}

async function loadTablesRefreshCount() {
  const res = await http.get('/tables')
  tables.value = res.tables
}

async function downloadTemplate() {
  const res = await http.get(`/tables/${activeId.value}/template`, { responseType: 'blob' })
  downloadBlob(res, `导入模板_${activeTable.value?.name || ''}.xlsx`)
}

function exportParams() {
  return {
    search: search.value,
    filters: JSON.stringify(filters.value),
    sort: sortKey.value,
    order: sortOrder.value
  }
}

async function doExport() {
  exporting.value = true
  try {
    const res = await http.get(`/tables/${activeId.value}/export`,
      { params: exportParams(), responseType: 'blob' })
    downloadBlob(res, `${activeTable.value?.name || '数据'}_导出.xlsx`)
    ElMessage.success('导出成功')
  } finally {
    exporting.value = false
  }
}

function onPageSize(size) {
  pageSize.value = size
  reload()
}

watch(mode, v => localStorage.setItem('dc-view-mode', v))

/* ---------------- 渲染辅助 ---------------- */

function colWidth(f) {
  return {
    text: 150, textarea: 200, number: 120, select: 150, multi_select: 180,
    radio: 150, checkbox: 180, switch: 90, date: 130, datetime: 175
  }[f.type] || 150
}

function fmtCell(v) {
  if (v === null || v === undefined) return ''
  if (Array.isArray(v)) return v.join('、')
  return String(v)
}
</script>

<style scoped>
.data-page { height: 100%; overflow: hidden; }

/* tabs 不再嵌卡片，样式走全局 .dc-tabs（style.css） */
.page-tabs { flex: none; }
.page-tabs :deep(.el-tabs__header) { margin: 0; }
.tab-label { display: inline-flex; align-items: center; gap: 5px; max-width: 240px; }
.tab-count {
  background: color-mix(in srgb, var(--dc-primary) 16%, transparent);
  color: var(--dc-primary);
  border-radius: 999px; padding: 0 8px; font-size: 11px; line-height: 17px;
}

.toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; padding: 10px 12px; flex-wrap: wrap; flex: none;
}
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.search-input { width: 230px; }
.total-hint { white-space: nowrap; }

.table-card { flex: 1; min-height: 200px; overflow: hidden; padding: 0; }

.pagination-card { padding: 8px 12px; flex: none; display: flex; justify-content: flex-end; }
.load-hint { text-align: center; font-size: 12px; padding: 6px 0 2px; flex: none; }

.cols-pop .cols-head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px;
}
.cols-pop .el-checkbox-group { display: flex; flex-direction: column; gap: 2px; }
.pop-sec { margin: 10px 0 4px; font-size: 12px; }
.pop-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 5px 0; font-size: 13px; color: var(--dc-text);
}

.import-upload { width: 100%; }
.import-fails .fail-row {
  font-size: 13px; color: var(--dc-text);
  padding: 5px 8px; border-radius: 6px; margin-bottom: 4px;
  background: var(--dc-bg-soft); text-align: left;
}

@media (max-width: 768px) {
  .data-page { overflow-y: auto; }
  .table-card { min-height: 55vh; }
  .search-input { width: 100%; }
  .toolbar-left, .toolbar-right { width: 100%; }
  .tab-label { max-width: 160px; }
}
</style>
