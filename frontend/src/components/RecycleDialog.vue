<template>
  <el-drawer v-model="show" title="回收站" size="min(880px, 96vw)" append-to-body
             :close-on-click-modal="false" @open="onOpen">
    <div class="rec-body">
      <!-- 工具栏 -->
      <div class="rec-toolbar">
        <div class="rec-filters">
          <el-select v-model="tableId" placeholder="全部数据表" clearable
                     class="rec-select" @change="load">
            <el-option v-for="t in tables" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
          <el-input v-model="search" placeholder="搜索图号 / 名称…" clearable :prefix-icon="Search"
                    class="rec-search" @input="debouncedLoad" @clear="load" />
        </div>
        <div class="rec-ops">
          <el-button type="primary" plain :icon="RefreshLeft" :disabled="!sel.length"
                     :loading="restoring" @click="onRestoreSel">
            恢复选中（{{ sel.length }}）
          </el-button>
          <el-button type="danger" plain :icon="Delete" :disabled="!sel.length"
                     :loading="deleting" @click="onDeleteSel">
            彻底删除选中（{{ sel.length }}）
          </el-button>
          <el-button type="danger" text bg :disabled="!items.length" @click="onClear">清空回收站</el-button>
        </div>
      </div>

      <!-- 列表 -->
      <div class="card rec-table-card" v-loading="loading">
        <el-table :data="items" stripe size="small" class="dc-table" height="100%"
                  @selection-change="s => (sel = s)">
          <template #empty>
            <el-empty description="回收站是空的" :image-size="72" />
          </template>
          <el-table-column type="selection" width="42" />
          <el-table-column type="expand" width="36">
            <template #default="{ row }">
              <div class="detail-wrap">
                <span v-for="(v, k) in row.data" :key="k" class="detail-kv">
                  {{ labelOf(k) }}：{{ fmtVal(v) }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="table_name" label="所属表" min-width="130" show-overflow-tooltip />
          <el-table-column label="图号" min-width="120" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="row-no">{{ row.data.drawing_no || '—' }}</span>
            </template>
          </el-table-column>
          <el-table-column label="名称" min-width="100" show-overflow-tooltip>
            <template #default="{ row }">{{ row.data.name || '—' }}</template>
          </el-table-column>
          <el-table-column label="申请人" min-width="80" show-overflow-tooltip>
            <template #default="{ row }">{{ row.data.applicant || '—' }}</template>
          </el-table-column>
          <el-table-column prop="created_by" label="删除人" width="90" show-overflow-tooltip />
          <el-table-column prop="deleted_at" label="删除时间" width="150" />
          <el-table-column label="操作" width="132" fixed="right" align="center">
            <template #default="{ row }">
              <div class="op-btns">
                <el-button size="small" type="primary" text bg @click="onRestore([row])">恢复</el-button>
                <el-button size="small" type="danger" text bg @click="onDelete([row])">彻底删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-if="items.length" class="muted rec-hint">
        共 {{ items.length }} 条 · 恢复时自动检测图号冲突，序号冲突将自动重排
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Delete, RefreshLeft } from '@element-plus/icons-vue'
import { http } from '@/api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'changed'])

const show = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})

const items = ref([])
const tables = ref([])
const tableId = ref(null)
const search = ref('')
const sel = ref([])
const loading = ref(false)
const restoring = ref(false)
const deleting = ref(false)

/* 常用字段中文标签（展开明细用） */
const LABELS = {
  sn: '序号', name: '名称', model: '型号', drawing_no: '图号', project: '工程/项目',
  applicant: '申请人', apply_time: '申请时间', remark: '备注', std_drawing: '标准图样',
  tower_no: '塔号', cross_arm: '横担', rod_length: '导电杆长度'
}
function labelOf(k) { return LABELS[k] || k }
function fmtVal(v) {
  if (Array.isArray(v)) return v.join('、') || '空'
  return String(v ?? '') || '空'
}

function onOpen() {
  tableId.value = null
  search.value = ''
  sel.value = []
  load()
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (tableId.value) params.table_id = tableId.value
    if (search.value) params.search = search.value
    const res = await http.get('/recycle', { params })
    items.value = res.items || []
    tables.value = res.tables || []
    sel.value = []
  } finally {
    loading.value = false
  }
}

let t = null
function debouncedLoad() {
  clearTimeout(t)
  t = setTimeout(load, 300)
}

/* 批量操作结果提示：成功条数 + 失败原因 */
function report(results, okText, failText) {
  const ok = results.filter(r => r.ok).length
  const fails = results.filter(r => !r.ok)
  if (ok) ElMessage.success(`${okText} ${ok} 条`)
  if (fails.length) {
    ElMessage.warning(`${failText} ${fails.length} 条：${fails[0].message}` +
      (fails.length > 1 ? ' 等' : ''))
  }
}

async function onRestore(rows) {
  restoring.value = true
  try {
    const res = await http.post('/recycle/restore', { ids: rows.map(r => r.id) })
    report(res.results || [], '已恢复', '未能恢复')
    if ((res.results || []).some(r => r.ok)) emit('changed')
    await load()
  } finally {
    restoring.value = false
  }
}
function onRestoreSel() { if (sel.value.length) onRestore(sel.value) }

async function onDelete(rows) {
  try {
    await ElMessageBox.confirm(
      `确定彻底删除选中的 ${rows.length} 条记录吗？彻底删除后无法恢复。`,
      '彻底删除确认', { type: 'warning', confirmButtonText: '彻底删除', cancelButtonText: '取消' })
  } catch { return }
  deleting.value = true
  try {
    const res = await http.post('/recycle/delete', { ids: rows.map(r => r.id) })
    report(res.results || [], '已彻底删除', '未能删除')
    if ((res.results || []).some(r => r.ok)) emit('changed')
    await load()
  } finally {
    deleting.value = false
  }
}
function onDeleteSel() { if (sel.value.length) onDelete(sel.value) }

async function onClear() {
  const scope = tableId.value
    ? `「${tables.value.find(t => t.id === tableId.value)?.name || ''}」的`
    : ''
  try {
    await ElMessageBox.confirm(
      `确定清空回收站中${scope || '全部'}记录吗？彻底删除后无法恢复。`,
      '清空回收站', { type: 'warning', confirmButtonText: '清空', cancelButtonText: '取消' })
  } catch { return }
  deleting.value = true
  try {
    const res = await http.post('/recycle/clear', tableId.value ? { table_id: tableId.value } : {})
    ElMessage.success(res.message || '已清空')
    emit('changed')
    await load()
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.rec-body {
  height: 100%; display: flex; flex-direction: column; gap: 12px;
  padding: 0 4px;
}
.rec-toolbar {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; flex-wrap: wrap; flex: none;
}
.rec-filters { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rec-select { width: 180px; }
.rec-search { width: 200px; }
.rec-ops { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.rec-table-card { flex: 1; min-height: 0; padding: 0; overflow: hidden; }
.rec-hint { text-align: center; font-size: 12px; padding: 2px 0; flex: none; }
.row-no { font-weight: 600; color: var(--dc-primary); font-size: 13px; }
.detail-wrap { padding: 2px 12px 10px; display: flex; flex-wrap: wrap; gap: 8px 20px; }
.detail-kv { font-size: 12.5px; color: var(--dc-text-soft); }

@media (max-width: 768px) {
  .rec-select, .rec-search { width: 100%; }
  .rec-filters, .rec-ops { width: 100%; }
  .rec-toolbar { gap: 8px; }
}
</style>
