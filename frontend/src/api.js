import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from './router'

export const http = axios.create({ baseURL: '/api', timeout: 60000 })

http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('dc-token')
  if (token) cfg.headers.Authorization = 'Bearer ' + token
  return cfg
})

http.interceptors.response.use(
  res => {
    if (res.data && res.data.ok === false) {
      const msg = res.data.message || '操作失败'
      if (!res.config.headers['X-Silent']) ElMessage.error(msg)
      return Promise.reject(Object.assign(new Error(msg), { response: res, handled: true }))
    }
    return res.data
  },
  err => {
    const resp = err.response
    const msg = resp?.data?.message || err.message || '网络异常'
    if (!err.config?.headers?.['X-Silent']) {
      ElMessage.error(msg)
      if (resp?.status === 401 && !resp.config.url.includes('/auth/')) {
        const cur = router.currentRoute.value
        if (cur.path !== '/login') {
          // 交给路由守卫处理
          router.push('/login').catch(() => {})
        }
      }
    }
    return Promise.reject(err)
  }
)

/** 下载 blob 文件 */
export function downloadBlob(data, filename) {
  const url = URL.createObjectURL(new Blob([data]))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
