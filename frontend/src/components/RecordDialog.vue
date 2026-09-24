<template>
  <el-dialog v-model="show" :title="title" width="860px" top="8vh"
             append-to-body destroy-on-close :close-on-click-modal="false" @open="onOpen">
    <el-form ref="formRef" :model="form" label-width="96px" label-position="left"
             class="rec-form" @submit.prevent="onSubmit">
      <el-row :gutter="16">
        <el-col v-for="f in fields" :key="f.key" :xs="24" :sm="12">
          <el-form-item :label="f.label" :prop="f.key"
                        :rules="rules(f)" :required="isShowRequired(f)">
            <!-- 序号：自动 -->
            <el-input v-if="f.key === 'sn'" :model-value="snDisplay" disabled>
              <template #suffix><span class="muted">自动</span></template>
            </el-input>
            <!-- 单选组 -->
            <el-radio-group v-else-if="f.type === 'radio'" v-model="form[f.key]">
              <el-radio v-for="o in opts(f.key)" :key="o" :value="o" border size="small">{{ o }}</el-radio>
            </el-radio-group>
            <!-- 开关 -->
            <el-switch v-else-if="f.type === 'switch'" v-model="form[f.key]" />
            <!-- 多选下拉（复选 / 多选） -->
            <el-select v-else-if="f.type === 'multi_select' || f.type === 'checkbox'"
                       v-model="form[f.key]" multiple filterable allow-create
                       default-first-option :reserve-keyword="false"
                       placeholder="可搜索，无则直接输入新建" clearable>
              <el-option v-for="o in opts(f.key)" :key="o" :label="o" :value="o" />
            </el-select>
            <!-- 可搜索下拉 -->
            <el-select v-else-if="f.type === 'select'" v-model="form[f.key]"
                       filterable allow-create default-first-option
                       placeholder="可搜索，无则直接输入新建" clearable>
              <el-option v-for="o in opts(f.key)" :key="o" :label="o" :value="o" />
            </el-select>
            <!-- 数字 -->
            <el-input-number v-else-if="f.type === 'number'" v-model="form[f.key]"
                             :controls="false" class="w-full" placeholder="留空自动生成" />
            <!-- 日期 -->
            <el-date-picker v-else-if="f.type === 'date'" v-model="form[f.key]"
                            type="date" value-format="YYYY-MM-DD" placeholder="选择日期"
                            class="w-full" />
            <!-- 日期时间 -->
            <el-date-picker v-else-if="f.type === 'datetime'" v-model="form[f.key]"
                            type="datetime" value-format="YYYY-MM-DD HH:mm:ss"
                            placeholder="留空自动记录当前时间" class="w-full"
                            :default-time="defaultTime" />
            <!-- 多行文本 -->
            <el-input v-else-if="f.type === 'textarea'" v-model="form[f.key]"
                      type="textarea" :rows="2" placeholder="" />
            <!-- 文本 -->
            <el-input v-else v-model="form[f.key]" placeholder="" />
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>
    <template #footer>
      <el-button @click="show = false">取 消</el-button>
      <el-button type="primary" :loading="saving" @click="onSubmit">
        {{ isEdit ? '保存修改' : '提交申请' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { http } from '@/api'

const props = defineProps({
  modelValue: Boolean,
  table: { type: Object, default: null },       // {id, name, fields, ...}
  record: { type: Object, default: null },      // 编辑时传入
  options: { type: Object, default: () => ({}) } // 各字段可选值
})
const emit = defineEmits(['update:modelValue', 'saved'])

const show = computed({
  get: () => props.modelValue,
  set: v => emit('update:modelValue', v)
})
const fields = computed(() => props.table?.fields || [])
const isEdit = computed(() => !!props.record)
const title = computed(() =>
  `${isEdit.value ? '编辑记录' : '申请图号'} · ${props.table?.name || ''}`)

const formRef = ref()
const form = reactive({})
const saving = ref(false)

const defaultTime = new Date(2000, 0, 1, 12, 0, 0)

const snDisplay = computed(() => {
  if (isEdit.value) return props.record?.data?.sn ?? ''
  return '自动生成'
})

function opts(key) { return props.options[key] || [] }
function isShowRequired(f) { return f.required && f.key !== 'sn' }

function rules(f) {
  if (!f.required || f.key === 'sn') return []
  return [{
    validator: (rule, value, cb) => {
      const v = Array.isArray(value) ? value.length : value
      if (v === '' || v === null || v === undefined) {
        cb(new Error(`请填写${f.label}`))
      } else cb()
    },
    trigger: ['blur', 'change']
  }]
}

function onOpen() {
  Object.keys(form).forEach(k => delete form[k])
  for (const f of fields.value) {
    let v = null
    if (isEdit.value) {
      v = props.record.data[f.key]
    } else {
      v = f.default_value ?? ''
    }
    if (f.key === 'sn') continue
    if (f.type === 'multi_select' || f.type === 'checkbox') {
      v = Array.isArray(v) ? v : (v ? [v] : [])
    }
    if (f.type === 'switch') v = v === '1' || v === 1 || v === true
    form[f.key] = v ?? (f.type === 'switch' ? false : null)
  }
}

async function onSubmit() {
  try {
    await formRef.value.validate()
  } catch { return }
  saving.value = true
  try {
    const payload = { data: { ...form } }
    if (isEdit.value) {
      const data = { ...props.record.data, ...form }
      delete data.sn
      await http.put(`/records/${props.record.id}`, { data })
      ElMessage.success('记录已更新')
    } else {
      delete payload.data.sn
      await http.post(`/tables/${props.table.id}/records`, payload)
      ElMessage.success('图号申请成功')
    }
    emit('saved')
    show.value = false
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.rec-form :deep(.el-form-item) { margin-bottom: 14px; }
.rec-form :deep(.el-form-item__label) { font-size: 13px; }
.w-full { width: 100%; }
</style>
