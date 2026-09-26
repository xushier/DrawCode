<template>
  <div class="login-bg">
    <div class="login-card">
      <div class="login-head" @click="aboutOpen = true">
        <Logo :size="52" />
        <div class="login-names">
          <div class="login-name">{{ store.site.name }}</div>
          <div class="login-sub">DrawCode · {{ store.site.subtitle }}</div>
        </div>
      </div>

      <!-- 登录 -->
      <template v-if="mode === 'login'">
        <el-form :model="form" @submit.prevent="onLogin" size="large" @keyup.enter="onLogin">
          <el-form-item>
            <el-input v-model="form.username" placeholder="账号" :prefix-icon="User"
                      autocomplete="username" autofocus />
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock"
                      show-password autocomplete="current-password" />
          </el-form-item>
          <el-button type="primary" class="login-btn" size="large" :loading="loading"
                     @click="onLogin">登 录</el-button>
        </el-form>
        <div v-if="store.allowRegister" class="mode-link muted">
          还没有账号？<el-link type="primary" :underline="false" @click="toRegister">立即注册</el-link>
        </div>
      </template>

      <!-- 注册 -->
      <template v-else>
        <el-form :model="reg" @submit.prevent="onRegister" size="large" @keyup.enter="onRegister">
          <div class="reg-tip">
            <el-icon><WarningFilled /></el-icon>
            建议使用<b>真实姓名</b>作为用户名，便于识别申请人
          </div>
          <el-form-item>
            <el-input v-model="reg.username" placeholder="用户名（建议真实姓名）" :prefix-icon="User"
                      autocomplete="off" maxlength="40" clearable />
          </el-form-item>
          <div v-if="unameState" class="uname-state" :class="unameState">
            <el-icon v-if="unameState === 'ok'"><CircleCheckFilled /></el-icon>
            <el-icon v-else-if="unameState === 'taken'"><CircleCloseFilled /></el-icon>
            {{ unameState === 'checking' ? '正在检测…' : unameState === 'ok' ? '该用户名可用' : '该用户名已被使用，请换一个' }}
          </div>
          <el-form-item>
            <el-input v-model="reg.password" type="password" placeholder="密码（至少 8 位）" :prefix-icon="Lock"
                      show-password autocomplete="new-password" maxlength="64" />
          </el-form-item>
          <el-form-item>
            <el-input v-model="reg.confirm" type="password" placeholder="确认密码" :prefix-icon="Lock"
                      show-password autocomplete="new-password" maxlength="64" />
          </el-form-item>
          <el-button type="primary" class="login-btn" size="large" :loading="loading"
                     @click="onRegister">注 册</el-button>
        </el-form>
        <div class="mode-link muted">
          已有账号？<el-link type="primary" :underline="false" @click="mode = 'login'">返回登录</el-link>
        </div>
      </template>

      <div class="login-foot muted">
        v{{ store.site.version }} · {{ store.site.author }}
      </div>
    </div>
    <AboutDialog v-model="aboutOpen" />
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, WarningFilled, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import { http } from '@/api'
import { useApp } from '@/store'
import Logo from '@/components/Logo.vue'
import AboutDialog from '@/components/AboutDialog.vue'

const store = useApp()
const router = useRouter()
const loading = ref(false)
const aboutOpen = ref(false)
const form = reactive({ username: '', password: '' })

const mode = ref('login')
const reg = reactive({ username: '', password: '', confirm: '' })
const unameState = ref('')   // '' | checking | ok | taken
let checkTimer = null

function toRegister() {
  reg.username = form.username || ''
  mode.value = 'register'
}

// 用户名防抖查重（500ms）
watch(() => reg.username, v => {
  clearTimeout(checkTimer)
  const name = (v || '').trim()
  unameState.value = ''
  if (!name) return
  unameState.value = 'checking'
  checkTimer = setTimeout(async () => {
    if ((reg.username || '').trim() !== name) return
    try {
      const res = await http.get('/auth/check-username',
        { params: { username: name }, headers: { 'X-Silent': 1 } })
      unameState.value = res.taken ? 'taken' : 'ok'
    } catch (e) { unameState.value = '' }
  }, 500)
})

async function onLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入账号与密码')
    return
  }
  loading.value = true
  try {
    await store.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } finally {
    loading.value = false
  }
}

async function onRegister() {
  const name = reg.username.trim()
  if (!name) { ElMessage.warning('请输入用户名'); return }
  if (name.length > 40) { ElMessage.warning('用户名需在 40 字以内'); return }
  if (unameState.value === 'taken') { ElMessage.warning('该用户名已被使用，请换一个'); return }
  if (reg.password.length < 8) { ElMessage.warning('密码至少 8 位'); return }
  if (reg.password !== reg.confirm) { ElMessage.warning('两次输入的密码不一致'); return }
  loading.value = true
  try {
    await store.register(name, reg.password)
    ElMessage.success('注册成功，已自动登录')
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-bg {
  height: 100vh;
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
  background:
    radial-gradient(ellipse 60% 50% at 70% 20%,
      color-mix(in srgb, var(--dc-primary) 22%, transparent), transparent),
    radial-gradient(ellipse 50% 40% at 20% 80%,
      color-mix(in srgb, var(--dc-primary) 16%, transparent), transparent),
    var(--dc-bg);
}
.login-card {
  width: 400px; max-width: 100%;
  background: var(--dc-card);
  border: 1px solid var(--dc-border);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(20, 40, 60, 0.1);
  padding: 34px 36px 24px;
}
.login-head {
  display: flex; align-items: center; gap: 16px;
  margin-bottom: 26px; cursor: pointer;
}
.login-name { font-size: 20px; font-weight: 700; color: var(--dc-text); line-height: 1.3; }
.login-sub { font-size: 13px; color: var(--dc-text-soft); margin-top: 3px; }
.login-btn { width: 100%; margin-top: 4px; letter-spacing: 6px; }
.login-foot { text-align: center; margin-top: 18px; font-size: 12px; }
.mode-link { text-align: center; margin-top: 14px; font-size: 13px; }
.reg-tip {
  display: flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: #b88230;
  background: #fff6e5; border: 1px solid #f5e3c2;
  border-radius: 8px; padding: 8px 12px; margin-bottom: 16px;
}
.reg-tip b { font-weight: 700; }
.uname-state {
  display: flex; align-items: center; gap: 4px;
  font-size: 12.5px; margin: -8px 0 12px 2px;
  min-height: 18px;
}
.uname-state.ok { color: #2f9e6e; }
.uname-state.taken { color: #d0443c; }
.uname-state.checking { color: var(--dc-text-soft); }

@media (max-width: 480px) {
  .login-card { padding: 26px 22px 18px; }
  .login-name { font-size: 17px; }
}
</style>
