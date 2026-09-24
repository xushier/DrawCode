<template>
  <div class="fp">
    <el-form label-width="88px" label-position="left" size="default" class="fp-form">
      <template v-for="f in editableFields" :key="f.key">
        <el-form-item v-if="isRange(f.type)" :label="f.label">
          <el-date-picker
            v-model="draft[f.key]"
            :type="f.type === 'date' ? 'daterange' : 'datetimerange'"
            :value-format="f.type === 'date' ? 'YYYY-MM-DD' : 'YYYY-MM-DD HH:mm:ss'"
            start-placeholder="开始" end-placeholder="结束"
            class="w-full" />
        </el-form-item>
        <el-form-item v-else-if="f.type === 'number'" :label="f.label">
          <div class="fp-num">
            <el-input-number v-model="draft[f.key][0]" :controls="false" placeholder="最小值" class="w-full" />
            <span class="muted">至</span>
            <el-input-number v-model="draft[f.key][1]" :controls="false" placeholder="最大值" class="w-full" />
          </div>
        </el-form-item>
        <el-form-item v-else-if="isSelect(f.type)" :label="f.label">
          <el-select v-model="draft[f.key]" multiple filterable clearable
                     collapse-tags collapse-tags-tooltip placeholder="选择或搜索" class="w-full">
            <el-option v-for="o in (options[f.key] || [])" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
        <el-form-item v-else-if="f.type === 'switch'" :label="f.label">
          <el-select v-model="draft[f.key]" clearable placeholder="全部" class="w-full">
            <el-option label="已开启" value="1" />
            <el-option label="已关闭" value="0" />
          </el-select>
        </el-form-item>
        <el-form-item v-else :label="f.label">
          <el-input v-model="draft[f.key]" placeholder="包含文字" clearable />
        </el-form-item>
      </template>
    </el-form>
    <div class="fp-foot">
      <span class="muted">{{ activeCount ? `已应用 ${activeCount} 项筛选` : '暂无筛选' }}</span>
      <div>
        <el-button size="small" @click="reset">重置</el-button>
        <el-button size="small" type="primary" @click="apply">应用筛选</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  options: { type: Object, default: () => ({}) },
  modelValue: { type: Object, default: () => ({}) }   // 当前已应用的 {key: {op, value}}
})
const emit = defineEmits(['update:modelValue'])

const editableFields = computed(() => props.fields.filter(f => f.key !== 'sn'))

const draft = reactive({})

function initDraft() {
  Object.keys(draft).forEach(k => delete draft[k])
  for (const f of editableFields.value) {
    if (isSelect(f.type)) draft[f.key] = []
    else if (f.type === 'number') draft[f.key] = [undefined, undefined]
    else draft[f.key] = ''
  }
  // 回填已应用值
  for (const [k, cond] of Object.entries(props.modelValue || {})) {
    if (!(k in draft)) continue
    if (cond.op === 'in') draft[k] = [...(cond.value || [])]
    else if (cond.op === 'range') {
      if (props.fields.find(f => f.key === k)?.type === 'number') draft[k] = cond.value
      else draft[k] = cond.value
    } else if (cond.op === 'eq') draft[k] = String(cond.value)
    else draft[k] = cond.value
  }
}

watch(() => props.fields, initDraft, { immediate: true })

function isSelect(t) { return ['select', 'multi_select', 'radio', 'checkbox'].includes(t) }
function isRange(t) { return ['date', 'datetime'].includes(t) }

const activeCount = computed(() => Object.keys(props.modelValue || {}).length)

function apply() {
  const ops = {}
  for (const f of editableFields.value) {
    const v = draft[f.key]
    if (isSelect(f.type)) {
      if (v && v.length) ops[f.key] = { op: 'in', value: v }
    } else if (f.type === 'number') {
      if (v[0] !== undefined && v[0] !== null || v[1] !== undefined && v[1] !== null) {
        ops[f.key] = { op: 'range', value: [v[0] ?? '', v[1] ?? ''] }
      }
    } else if (isRange(f.type)) {
      if (Array.isArray(v) && v.length === 2 && v[0] && v[1]) {
        ops[f.key] = { op: 'range', value: v }
      }
    } else if (f.type === 'switch') {
      if (v !== '' && v !== undefined) ops[f.key] = { op: 'eq', value: v }
    } else {
      if (v && String(v).trim()) ops[f.key] = { op: 'like', value: String(v).trim() }
    }
  }
  emit('update:modelValue', ops)
}

function reset() {
  initDraft()
  emit('update:modelValue', {})
}
</script>

<style scoped>
.fp { width: 300px; }
.fp-form :deep(.el-form-item) { margin-bottom: 10px; }
.fp-num { display: flex; align-items: center; gap: 6px; width: 100%; }
.fp-foot {
  display: flex; justify-content: space-between; align-items: center;
  margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--dc-border);
}
.w-full { width: 100%; }
</style>
