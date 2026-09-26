<template>
  <div class="page settings-page">
    <el-tabs v-model="tab" class="settings-tabs dc-tabs">
      <!-- 基本设置 -->
      <el-tab-pane label="基本设置" name="basic">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">基本设置</div>
            <el-form label-width="120px" class="set-form">
              <el-form-item label="机构名称">
                <el-input v-model="form.site_org" placeholder="如：智能装备研究院" style="max-width: 320px" />
                <div class="field-hint muted">
                  系统全称：智能「{{ form.site_org }}」图号系统 · 副标题：「{{ form.site_org }}」图号系统
                </div>
              </el-form-item>
              <el-form-item label="访客模式">
                <el-switch v-model="guestModeBool" />
                <div class="field-hint muted">开启后，未登录的访客可浏览图号数据并申请图号（仅新增）</div>
              </el-form-item>
              <el-form-item label="日志自动清理">
                <div class="inline-row">
                  <el-switch v-model="logAutoBool" />
                  <el-input-number v-model="form.log_retention_days" :min="1" :max="365"
                                   :disabled="!logAutoBool" controls-position="right" style="width: 120px" />
                  <span class="muted">天</span>
                </div>
                <div class="field-hint muted">系统日志将定期自动清理，保留最近指定天数的记录</div>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="saving" @click="saveBasic">保存设置</el-button>
              </el-form-item>
            </el-form>
          </div>
        </div>
      </el-tab-pane>

      <!-- 表管理 -->
      <el-tab-pane label="表管理" name="tables">
        <div class="pane pane-table">
          <div class="pane-head">
            <div class="pane-title">数据表管理</div>
            <el-button type="primary" :icon="Plus" @click="newTableOpen = true">新建表</el-button>
          </div>
          <el-table :data="tables" stripe size="small" class="dc-table">
            <el-table-column prop="name" label="表名" min-width="180">
              <template #default="{ row }">
                <el-tag v-if="row.is_system" size="small" effect="plain" style="margin-right: 6px">内置</el-tag>
                {{ row.name }}
              </template>
            </el-table-column>
            <el-table-column prop="count" label="数据量" width="90" align="center" />
            <el-table-column label="字段数" width="90" align="center">
              <template #default="{ row }">{{ row.fields?.length || 0 }}</template>
            </el-table-column>
            <el-table-column label="操作" width="232" align="center">
              <template #default="{ row }">
                <div class="op-btns">
                  <el-button size="small" type="primary" text bg @click="openFields(row)">字段管理</el-button>
                  <el-button size="small" text bg @click="renameTable(row)">重命名</el-button>
                  <el-button v-if="!row.is_system" size="small" type="danger" text bg @click="deleteTable(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 通知 -->
      <el-tab-pane label="微信通知" name="notify">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">微信通知</div>
            <el-form label-width="130px" class="set-form">
            <el-form-item label="启用通知">
              <el-switch v-model="notifyOn" />
            </el-form-item>
            <el-form-item label="通知渠道">
              <el-radio-group v-model="form.notify_type" :disabled="!notifyOn">
                <el-radio value="robot">企业微信群机器人</el-radio>
                <el-radio value="wecom_app">企业微信应用通知</el-radio>
              </el-radio-group>
            </el-form-item>
            <template v-if="form.notify_type === 'robot'">
              <el-form-item label="Webhook 地址">
                <el-input v-model="form.notify_webhook" :disabled="!notifyOn"
                          placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=…"
                          style="max-width: 520px" />
              </el-form-item>
            </template>
            <template v-else>
              <el-form-item label="企业 ID">
                <el-input v-model="form.notify_corpid" :disabled="!notifyOn"
                          placeholder="企业微信管理后台 - 我的企业 - 企业信息" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="应用密钥">
                <el-input v-model="form.notify_secret" :disabled="!notifyOn" show-password
                          placeholder="自建应用的 Secret" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="应用 AgentId">
                <el-input v-model="form.notify_agentid" :disabled="!notifyOn"
                          placeholder="自建应用的 AgentId" style="max-width: 320px" />
              </el-form-item>
              <el-form-item label="指定接收人">
                <el-input v-model="form.notify_touser" :disabled="!notifyOn"
                          placeholder="成员账号，多人用 | 分隔，默认 @all" style="max-width: 320px" />
              </el-form-item>
            </template>
            <el-form-item label="消息类型">
              <el-radio-group v-model="form.notify_style" :disabled="!notifyOn">
                <el-radio value="text">文字消息</el-radio>
                <el-radio value="image_text">图文消息</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="通知字体">
              <div class="font-manage">
                <div class="font-row">
                  <el-select v-model="form.notify_font" :disabled="!notifyOn" style="width: 240px">
                    <el-option label="系统默认字体" value="" />
                    <el-option v-for="f in fonts" :key="f.name" :label="f.name" :value="f.name" />
                  </el-select>
                  <el-upload :show-file-list="false" :auto-upload="false" accept=".ttf,.otf,.ttc"
                             :disabled="!notifyOn" :on-change="onFontUpload">
                    <el-button :disabled="!notifyOn" :loading="fontUploading">上传字体</el-button>
                  </el-upload>
                </div>
                <div v-if="fonts.length" class="font-list">
                  <div v-for="f in fonts" :key="f.name" class="font-item">
                    <span class="font-name" :title="f.name">{{ f.name }}</span>
                    <span class="muted font-size">{{ fmtSize(f.size) }}</span>
                    <el-button size="small" type="danger" text bg @click="delFont(f)">删除</el-button>
                  </div>
                </div>
                <div class="field-hint muted">封面图使用的字体，可上传中文 TTF / OTF 字体，选择后点击「保存设置」生效</div>
              </div>
            </el-form-item>
            <el-form-item label="触发事件">
              <div class="inline-row">
                <el-checkbox v-model="notifyAdd" :disabled="!notifyOn">新增图号时通知</el-checkbox>
                <el-checkbox v-model="notifyDel" :disabled="!notifyOn">删除图号时通知</el-checkbox>
              </div>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="saving" @click="saveNotify">保存设置</el-button>
              <el-button :disabled="!notifyOn" :loading="testing" @click="testNotify">发送测试通知</el-button>
            </el-form-item>
          </el-form>
          </div>
        </div>
      </el-tab-pane>

      <!-- 个性化 -->
      <el-tab-pane label="个性化" name="theme">
        <div class="pane">
          <div class="pane-center pane-theme">
            <div class="pane-title">主题与外观</div>
            <div class="theme-grid">
              <div v-for="t in THEMES" :key="t.id" class="theme-card"
                   :class="{ active: store.theme === t.id }" @click="store.setTheme(t.id)">
                <div class="theme-colors">
                  <span :style="{ background: t.color }" />
                  <span :style="{ background: mix(t.color) }" />
                </div>
                <div class="theme-name">{{ t.name }}</div>
                <el-icon v-if="store.theme === t.id" class="theme-check"><Check /></el-icon>
              </div>
            </div>
            <div class="dark-row">
              <div>
                <div>暗色模式</div>
                <div class="muted" style="font-size: 12px">深色背景下同色系低亮度配色</div>
              </div>
              <el-switch :model-value="store.dark" @update:model-value="store.setDark" />
            </div>
            <div class="dark-row">
              <div>
                <div>表格边框</div>
                <div class="muted" style="font-size: 12px">开启后所有表格显示列分隔线，全局生效</div>
              </div>
              <el-switch :model-value="store.vborder" @update:model-value="store.setVborder" />
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 账户安全 -->
      <el-tab-pane label="账户安全" name="security">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">账户安全</div>
            <el-form label-width="90px" class="set-form" ref="pwdFormRef" :model="pwd">
              <el-form-item label="原密码">
                <el-input v-model="pwd.old" type="password" show-password />
              </el-form-item>
              <el-form-item label="新密码">
                <el-input v-model="pwd.new" type="password" show-password placeholder="至少 4 位" />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input v-model="pwd.confirm" type="password" show-password />
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="pwdSaving" @click="changePwd">修改密码</el-button>
              </el-form-item>
            </el-form>
            <div class="avatar-row">
              <el-avatar :size="56" :src="avatarUrl"
                         style="background: var(--dc-primary); font-size: 22px; flex: none">A</el-avatar>
              <div class="avatar-info">
                <div class="avatar-name">{{ store.user?.username || 'admin' }}</div>
                <div class="muted" style="font-size: 12px">支持 PNG / JPG / GIF / WebP，上传后自动替换旧头像</div>
              </div>
              <el-upload :show-file-list="false" :auto-upload="false" accept="image/*"
                         :on-change="onAvatarChange">
                <el-button>更换头像</el-button>
              </el-upload>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- 备份恢复 -->
      <el-tab-pane label="备份恢复" name="backup">
        <div class="pane pane-backup">
          <div class="pane-head">
            <div class="pane-title">备份与恢复</div>
            <div class="backup-actions">
              <el-switch v-model="autoBackup" active-text="每日自动备份" @change="onAutoBackup" />
              <el-button type="primary" :icon="FolderAdd" :loading="backing" @click="doBackup">立即备份</el-button>
            </div>
          </div>
          <el-table :data="backups" stripe size="small" class="dc-table" v-loading="backupsLoading">
            <template #empty>
              <el-empty description="暂无备份，点击「立即备份」创建" :image-size="64" />
            </template>
            <el-table-column prop="name" label="文件名" min-width="230" show-overflow-tooltip />
            <el-table-column label="大小" width="90" align="center">
              <template #default="{ row }">{{ fmtSize(row.size) }}</template>
            </el-table-column>
            <el-table-column prop="created_at" label="备份时间" width="165" align="center" />
            <el-table-column label="操作" width="196" align="center">
              <template #default="{ row }">
                <div class="op-btns">
                  <el-button size="small" type="primary" text bg @click="downloadBk(row)">下载</el-button>
                  <el-button size="small" text bg @click="restoreBk(row)">恢复</el-button>
                  <el-button size="small" type="danger" text bg @click="deleteBk(row)">删除</el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
          <div class="muted backup-tip">
            备份包含全部图号数据与系统数据，保存在服务器数据目录 backups 下，最多保留 10 个。
            恢复将用备份文件覆盖当前全部数据，请谨慎操作。
          </div>
        </div>
      </el-tab-pane>

      <!-- 关于 -->
      <el-tab-pane label="关于" name="about">
        <div class="pane">
          <div class="pane-center">
            <div class="pane-title">关于系统</div>
          <div class="about-hero">
            <Logo :size="56" />
            <div>
              <div class="about-full">{{ store.site.name }}</div>
              <div class="muted">DrawCode · {{ store.site.subtitle }}</div>
            </div>
          </div>
          <div class="about-items">
            <div class="about-li"><span class="muted">版本</span><b>v{{ store.site.version }}</b></div>
            <div class="about-li"><span class="muted">作者</span><b>{{ store.site.author }}</b></div>
            <div class="about-li">
              <span class="muted">GitHub</span>
              <el-link type="primary" :href="store.site.github" target="_blank">{{ store.site.github }}</el-link>
            </div>
          </div>
          <div class="muted about-log-title">更新内容</div>
          <div v-for="log in store.site.changelog" :key="log.version" class="changelog">
            <b>v{{ log.version }}（{{ log.date }}）</b>
            <ul>
              <li v-for="i in log.items" :key="i">{{ i }}</li>
            </ul>
          </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建表 -->
    <el-dialog v-model="newTableOpen" title="新建数据表" width="460px" append-to-body destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="表名" required>
          <el-input v-model="newTableName" placeholder="请输入新表名称" maxlength="40" />
        </el-form-item>
        <el-form-item label="字段模板">
          <el-radio-group v-model="newTableTemplate" class="tpl-group">
            <el-radio value="blank" border size="small">空白自定义</el-radio>
            <el-radio v-for="(t, i) in sysTables" :key="t.id" :value="`t${i + 1}`" border size="small">
              {{ t.name }}
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newTableOpen = false">取 消</el-button>
        <el-button type="primary" :loading="creatingTable" @click="createTable">创 建</el-button>
      </template>
    </el-dialog>

    <!-- 字段管理 -->
    <el-dialog v-model="fieldsOpen" :title="`字段管理 · ${fieldsTable?.name || ''}`"
               width="720px" append-to-body destroy-on-close>
      <div class="fields-head">
        <span class="muted">内置字段不可删除；下拉类字段的新值将自动加入可选值</span>
        <el-button type="primary" size="small" :icon="Plus" @click="openFieldEdit(null)">添加字段</el-button>
      </div>
      <el-table :data="editFields" stripe size="small" class="dc-table">
        <el-table-column prop="label" label="字段名" min-width="110">
          <template #default="{ row }">
            <el-icon v-if="row.is_system" style="color: var(--dc-primary)"><Lock /></el-icon>
            {{ row.label }}
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ typeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="60" align="center">
          <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="default_value" label="默认值" width="90" show-overflow-tooltip>
          <template #default="{ row }">{{ row.default_value || '—' }}</template>
        </el-table-column>
        <el-table-column label="可选值" min-width="140">
          <template #default="{ row }">
            <template v-if="isSelType(row.type)">
              <el-tag v-for="o in (row.options || []).slice(0, 3)" :key="o" size="small"
                      style="margin-right: 4px" effect="plain">{{ o }}</el-tag>
              <span v-if="(row.options || []).length > 3" class="muted">+{{ row.options.length - 3 }}</span>
              <span v-if="!(row.options || []).length" class="muted">暂无</span>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="132" align="center">
          <template #default="{ row }">
            <div class="op-btns">
              <el-button size="small" type="primary" text bg @click="openFieldEdit(row)">编辑</el-button>
              <el-button v-if="!row.is_system" size="small" type="danger" text bg @click="deleteField(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 字段编辑 -->
    <el-dialog v-model="fieldOpen" :title="fieldForm.id ? '编辑字段' : '添加字段'"
               width="480px" append-to-body destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="字段名称" required>
          <el-input v-model="fieldForm.label" :disabled="fieldForm.is_system" maxlength="20"
                    placeholder="如：设计负责人" />
        </el-form-item>
        <el-form-item label="字段类型">
          <el-select v-model="fieldForm.type" :disabled="fieldForm.is_system" class="w-full">
            <el-option v-for="(label, t) in FIELD_TYPES" :key="t" :label="label" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="是否必填">
          <el-switch v-model="fieldForm.required" />
        </el-form-item>
        <el-form-item v-if="!isSelType(fieldForm.type)" label="默认值">
          <el-date-picker v-if="fieldForm.type === 'date'" v-model="fieldForm.default_value"
                          type="date" value-format="YYYY-MM-DD" class="w-full" />
          <el-date-picker v-else-if="fieldForm.type === 'datetime'" v-model="fieldForm.default_value"
                          type="datetime" value-format="YYYY-MM-DD HH:mm:ss" class="w-full" />
          <el-switch v-else-if="fieldForm.type === 'switch'" v-model="fieldForm.default_value" />
          <el-input v-else v-model="fieldForm.default_value" placeholder="留空则无默认值" />
        </el-form-item>
        <el-form-item v-if="isSelType(fieldForm.type)" label="可选值">
          <el-select v-model="fieldForm.options" multiple filterable allow-create
                     default-first-option placeholder="输入后回车添加，可预先配置" class="w-full">
            <el-option v-for="o in fieldForm.options" :key="o" :label="o" :value="o" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fieldOpen = false">取 消</el-button>
        <el-button type="primary" :loading="savingField" @click="saveField">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, FolderAdd } from '@element-plus/icons-vue'
import { http, downloadBlob } from '@/api'
import { useApp, THEMES } from '@/store'
import Logo from '@/components/Logo.vue'

const store = useApp()
const route = useRoute()
const router = useRouter()

const tab = ref('basic')
watch(tab, () => router.replace({ query: { ...route.query, tab: tab.value } }))

const FIELD_TYPES = {
  text: '文本', textarea: '多行文本', number: '数字', select: '可搜索下拉',
  multi_select: '多选下拉', radio: '单选组', checkbox: '复选组', switch: '开关',
  date: '日期', datetime: '日期时间'
}
const typeLabel = t => FIELD_TYPES[t] || t
const isSelType = t => ['select', 'multi_select', 'radio', 'checkbox'].includes(t)
const mix = c => `color-mix(in srgb, ${c} 40%, #e8edf2)`

/* ---------------- 基本设置 ---------------- */
const form = reactive({})
const saving = ref(false)
const guestModeBool = ref(false)
const logAutoBool = ref(false)
const notifyOn = ref(false)
const notifyAdd = ref(true)
const notifyDel = ref(true)
const testing = ref(false)

watch(guestModeBool, v => { form.guest_mode = v ? '1' : '0' })
watch(logAutoBool, v => { form.log_auto_clear = v ? '1' : '0' })
watch(notifyOn, v => { form.notify_enabled = v ? '1' : '0' })
watch(notifyAdd, v => { form.notify_on_add = v ? '1' : '0' })
watch(notifyDel, v => { form.notify_on_delete = v ? '1' : '0' })

async function loadSettings() {
  const res = await http.get('/settings')
  Object.assign(form, res.settings)
  guestModeBool.value = form.guest_mode === '1'
  logAutoBool.value = form.log_auto_clear === '1'
  notifyOn.value = form.notify_enabled === '1'
  notifyAdd.value = form.notify_on_add === '1'
  notifyDel.value = form.notify_on_delete === '1'
}

async function saveBasic() {
  if (!form.site_org?.trim()) return ElMessage.warning('机构名称不能为空')
  saving.value = true
  try {
    await http.put('/settings', {
      site_org: form.site_org.trim(), guest_mode: form.guest_mode,
      log_auto_clear: form.log_auto_clear, log_retention_days: String(form.log_retention_days)
    })
    await store.init()
    ElMessage.success('设置已保存')
  } finally { saving.value = false }
}

async function saveNotify() {
  saving.value = true
  try {
    await http.put('/settings', {
      notify_enabled: form.notify_enabled, notify_type: form.notify_type,
      notify_webhook: form.notify_webhook, notify_corpid: form.notify_corpid,
      notify_secret: form.notify_secret, notify_agentid: form.notify_agentid,
      notify_touser: form.notify_touser, notify_style: form.notify_style,
      notify_font: form.notify_font || '',
      notify_on_add: form.notify_on_add, notify_on_delete: form.notify_on_delete
    })
    ElMessage.success('通知设置已保存')
  } finally { saving.value = false }
}

/* ---------------- 通知字体 ---------------- */
const fonts = ref([])
const fontUploading = ref(false)

async function loadFonts() {
  const res = await http.get('/notify/fonts')
  fonts.value = res.fonts || []
}

async function onFontUpload(file) {
  const fd = new FormData()
  fd.append('file', file.raw)
  fontUploading.value = true
  try {
    const res = await http.post('/notify/fonts', fd)
    ElMessage.success(`字体「${res.name}」已上传，已自动选中`)
    form.notify_font = res.name
    await loadFonts()
  } finally { fontUploading.value = false }
}

async function delFont(f) {
  try {
    await ElMessageBox.confirm(`确定删除字体「${f.name}」吗？`, '删除字体',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.delete(`/notify/fonts/${encodeURIComponent(f.name)}`)
  if (form.notify_font === f.name) form.notify_font = ''
  ElMessage.success('已删除')
  await loadFonts()
}

async function testNotify() {
  testing.value = true
  try {
    await saveNotify()
    const res = await http.post('/notify/test')
    if (res.ok) ElMessage.success(res.message || '测试通知已发送')
    else ElMessage.error(res.message || '发送失败')
  } finally { testing.value = false }
}

/* ---------------- 备份与恢复 ---------------- */
const backups = ref([])
const backupsLoading = ref(false)
const backing = ref(false)
const autoBackup = ref(true)

async function loadBackups() {
  backupsLoading.value = true
  try {
    const res = await http.get('/backups')
    backups.value = res.items || []
    autoBackup.value = !!res.enabled
  } finally { backupsLoading.value = false }
}

async function onAutoBackup(v) {
  await http.put('/settings', { backup_enabled: v ? '1' : '0' })
  ElMessage.success(v ? '已开启每日自动备份' : '已关闭自动备份')
}

async function doBackup() {
  backing.value = true
  try {
    await http.post('/backups')
    ElMessage.success('备份完成')
    await loadBackups()
  } finally { backing.value = false }
}

function fmtSize(n) {
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB'
  if (n >= 1024) return (n / 1024).toFixed(1) + ' KB'
  return n + ' B'
}

async function downloadBk(row) {
  const res = await http.get(`/backups/${row.name}/download`, { responseType: 'blob' })
  downloadBlob(res, row.name)
}

async function restoreBk(row) {
  try {
    await ElMessageBox.confirm(
      `确定用备份「${row.name}」覆盖当前全部数据吗？此操作不可撤销。`,
      '恢复备份', { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' })
  } catch { return }
  const res = await http.post('/backups/restore', { name: row.name })
  ElMessage.success(res.message || '恢复完成，即将刷新页面')
  setTimeout(() => location.reload(), 900)
}

async function deleteBk(row) {
  try {
    await ElMessageBox.confirm(`确定删除备份「${row.name}」吗？`, '删除备份',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.delete(`/backups/${row.name}`)
  ElMessage.success('已删除')
  await loadBackups()
}

/* ---------------- 表管理 ---------------- */
const tables = ref([])
const sysTables = computed(() => tables.value.filter(t => t.is_system))
const newTableOpen = ref(false)
const newTableName = ref('')
const newTableTemplate = ref('blank')
const creatingTable = ref(false)

const fieldsOpen = ref(false)
const fieldsTable = ref(null)
const editFields = ref([])
const fieldOpen = ref(false)
const savingField = ref(false)
const fieldForm = reactive({
  id: null, table_id: null, label: '', type: 'text', required: false,
  default_value: '', options: [], is_system: false
})

async function loadTables() {
  const res = await http.get('/tables')
  tables.value = res.tables
}

async function createTable() {
  if (!newTableName.value.trim()) return ElMessage.warning('请输入表名')
  creatingTable.value = true
  try {
    await http.post('/tables', { name: newTableName.value.trim(), template: newTableTemplate.value })
    ElMessage.success('数据表已创建')
    newTableOpen.value = false
    newTableName.value = ''
    newTableTemplate.value = 'blank'
    loadTables()
  } finally { creatingTable.value = false }
}

async function renameTable(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的表名', '重命名数据表', {
      inputValue: row.name, inputPattern: /\S+/, inputErrorMessage: '表名不能为空',
      confirmButtonText: '保存', cancelButtonText: '取消'
    })
    await http.put(`/tables/${row.id}`, { name: value.trim() })
    ElMessage.success('已重命名')
    loadTables()
    store.init()
  } catch { /* 取消 */ }
}

async function deleteTable(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除「${row.name}」吗？该表 ${row.count} 条数据将一并删除，不可恢复。`,
      '删除数据表', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.delete(`/tables/${row.id}`)
  ElMessage.success('数据表已删除')
  loadTables()
}

function openFields(row) {
  fieldsTable.value = row
  editFields.value = row.fields || []
  fieldsOpen.value = true
}

function openFieldEdit(f) {
  if (f) {
    Object.assign(fieldForm, {
      id: f.id, table_id: fieldsTable.value.id, label: f.label, type: f.type,
      required: !!f.required, default_value: f.default_value || '',
      options: [...(f.options || [])], is_system: !!f.is_system
    })
  } else {
    Object.assign(fieldForm, {
      id: null, table_id: fieldsTable.value.id, label: '', type: 'text',
      required: false, default_value: '', options: [], is_system: false
    })
  }
  fieldOpen.value = true
}

async function saveField() {
  if (!fieldForm.label.trim()) return ElMessage.warning('请填写字段名称')
  savingField.value = true
  try {
    const payload = {
      label: fieldForm.label.trim(), type: fieldForm.type,
      required: fieldForm.required ? 1 : 0,
      default_value: String(fieldForm.default_value ?? ''),
      options: fieldForm.options
    }
    if (fieldForm.id) await http.put(`/fields/${fieldForm.id}`, payload)
    else await http.post(`/tables/${fieldForm.table_id}/fields`, payload)
    ElMessage.success('字段已保存')
    fieldOpen.value = false
    await loadTables()
    const t = tables.value.find(x => x.id === fieldForm.table_id)
    if (t) {
      fieldsTable.value = t
      editFields.value = t.fields || []
    }
  } finally { savingField.value = false }
}

async function deleteField(f) {
  try {
    await ElMessageBox.confirm(
      `确定删除字段「${f.label}」吗？记录中的该字段数据将一并清除。`,
      '删除字段', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch { return }
  await http.delete(`/fields/${f.id}`)
  ElMessage.success('字段已删除')
  await loadTables()
  const t = tables.value.find(x => x.id === fieldsTable.value.id)
  if (t) {
    fieldsTable.value = t
    editFields.value = t.fields || []
  }
}

/* ---------------- 账户安全 ---------------- */
const pwd = reactive({ old: '', new: '', confirm: '' })
const pwdSaving = ref(false)
const avatarStamp = ref(0)
const avatarUrl = computed(() =>
  store.user?.avatar ? `${store.user.avatar}?t=${avatarStamp.value}` : '')

async function changePwd() {
  if (!pwd.new || pwd.new.length < 4) return ElMessage.warning('新密码至少 4 位')
  if (pwd.new !== pwd.confirm) return ElMessage.warning('两次输入的密码不一致')
  pwdSaving.value = true
  try {
    await http.post('/auth/password', { old: pwd.old, new: pwd.new, confirm: pwd.confirm })
    ElMessage.success('密码已修改，请重新登录')
    await store.logout()
    router.push('/login')
  } finally { pwdSaving.value = false }
}

async function onAvatarChange(file) {
  const fd = new FormData()
  fd.append('file', file.raw)
  const res = await http.post('/auth/avatar', fd)
  store.user.avatar = res.avatar
  avatarStamp.value = Date.now()
  ElMessage.success('头像已更新')
}

onMounted(() => {
  if (route.query.tab) tab.value = String(route.query.tab)
  loadSettings()
  loadTables()
  loadBackups()
  loadFonts()
})
</script>

<style scoped>
.settings-page { height: 100%; overflow: hidden; }
.settings-tabs { height: 100%; background: transparent; display: flex; flex-direction: column; }
/* 横向 tabs：样式走全局 .dc-tabs，此处只管布局 */
.settings-tabs :deep(.el-tabs__header) { margin: 0 0 12px; flex: none; }
.settings-tabs :deep(.el-tabs__content) { flex: 1; min-height: 0; overflow-y: auto; }
.pane {
  background: var(--dc-card); border: 1px solid var(--dc-border);
  border-radius: var(--dc-radius); padding: 20px;
  width: fit-content; min-width: 560px; max-width: 760px;
}
/* 表管理页保持通栏卡片 */
.pane.pane-table { width: 100%; min-width: 0; max-width: none; }
/* 备份页：表单头 + 表格 + 提示 */
.pane-backup { min-width: 700px; }
.backup-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.backup-tip { margin-top: 12px; font-size: 12px; line-height: 1.6; }

/* 通知字体管理 */
.font-manage { width: 100%; max-width: 460px; }
.font-row { display: flex; align-items: center; gap: 10px; }
.font-list { margin-top: 10px; display: flex; flex-direction: column; gap: 6px; }
.font-item {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; border: 1px solid var(--dc-border);
  border-radius: 8px; font-size: 13px;
}
.font-item .font-name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.font-item .font-size { font-size: 12px; flex: none; }
.font-manage .field-hint { margin-top: 8px; }


.pane-title { font-size: 16px; font-weight: 700; margin-bottom: 18px; }
.pane-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
.pane-head .pane-title { margin-bottom: 0; }
.pane-center { width: 100%; }
.set-form { max-width: 680px; }
.field-hint { font-size: 12px; width: 100%; margin-top: 3px; }
.inline-row { display: flex; align-items: center; gap: 10px; }

.theme-grid { display: grid; grid-template-columns: repeat(3, minmax(120px, 1fr)); gap: 12px; margin-bottom: 16px; }
.theme-card {
  position: relative; border: 2px solid var(--dc-border); border-radius: var(--dc-radius);
  padding: 12px 10px; cursor: pointer; text-align: center; transition: all .18s;
}
.theme-card:hover { border-color: var(--dc-primary); }
.theme-card.active { border-color: var(--dc-primary); background: var(--dc-primary-soft); }
.theme-colors { display: flex; gap: 6px; justify-content: center; margin-bottom: 8px; }
.theme-colors span { width: 30px; height: 14px; border-radius: 6px; display: block; }
.theme-name { font-size: 13px; font-weight: 600; }
.theme-check { position: absolute; top: 6px; right: 8px; color: var(--dc-primary); }
.dark-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border: 1px solid var(--dc-border); border-radius: var(--dc-radius);
  width: 100%;
}
.dark-row + .dark-row { margin-top: 12px; }
.about-log-title { margin: 20px 0 8px; }

.avatar-row {
  display: flex; align-items: center; gap: 14px;
  padding-top: 20px; margin-top: 22px;
  border-top: 1px solid var(--dc-border);
}
.avatar-info { flex: 1; min-width: 0; }
.avatar-name { font-size: 15px; font-weight: 600; margin-bottom: 2px; }

.about-hero { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.about-full { font-size: 19px; font-weight: 700; }
.about-items { display: flex; flex-direction: column; gap: 8px; }
.about-li { display: flex; align-items: center; gap: 12px; font-size: 14px; }
.about-li span:first-child { width: 70px; }
.changelog b { font-size: 13px; }
.changelog ul { margin: 6px 0 14px; padding-left: 18px; }
.changelog li { font-size: 13px; color: var(--dc-text-soft); line-height: 1.8; }

.fields-head {
  display: flex; justify-content: space-between; align-items: center;
  gap: 10px; margin-bottom: 10px;
}
.tpl-group { display: flex; flex-wrap: wrap; gap: 8px; row-gap: 8px; }
.tpl-group :deep(.el-radio) { margin-right: 0; }
.w-full { width: 100%; }

@media (max-width: 768px) {
  .settings-page { overflow-y: auto; }
  .theme-grid { grid-template-columns: repeat(2, 1fr); }
  .pane { width: 100%; min-width: 0; max-width: none; }
  /* 表单改纵向标签（标签置顶）：释放被固定 120/130px 标签列挤占的内容宽度，
     使下拉/复选框/按钮等不再被压缩换行 */
  .pane .set-form :deep(.el-form-item) { display: block; }
  .pane .set-form :deep(.el-form-item__label) {
    width: auto !important;
    display: block;
    text-align: left;
    padding: 0;
    margin-bottom: 6px;
  }
  .pane .set-form :deep(.el-form-item__content) { margin-left: 0 !important; }
  .inline-row { flex-wrap: wrap; }
}
</style>
