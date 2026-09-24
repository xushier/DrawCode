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
      <el-form :model="form" @submit.prevent="onLogin" size="large" @keyup.enter="onLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="管理员账号" :prefix-icon="User"
                    autocomplete="username" autofocus />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" :prefix-icon="Lock"
                    show-password autocomplete="current-password" />
        </el-form-item>
        <el-button type="primary" class="login-btn" size="large" :loading="loading"
                   @click="onLogin">登 录</el-button>
      </el-form>
      <div class="login-foot muted">
        v{{ store.site.version }} · {{ store.site.author }}
      </div>
    </div>
    <AboutDialog v-model="aboutOpen" />
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useApp } from '@/store'
import Logo from '@/components/Logo.vue'
import AboutDialog from '@/components/AboutDialog.vue'

const store = useApp()
const router = useRouter()
const loading = ref(false)
const aboutOpen = ref(false)
const form = reactive({ username: 'admin', password: '' })

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

@media (max-width: 480px) {
  .login-card { padding: 26px 22px 18px; }
  .login-name { font-size: 17px; }
}
</style>
