import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach JWT from localStorage
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('access_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auto-refresh on 401
api.interceptors.response.use(
  r => r,
  async err => {
    const orig = err.config
    if (err.response?.status === 401 && !orig._retry) {
      orig._retry = true
      try {
        const refresh = localStorage.getItem('refresh_token')
        const { data } = await axios.post('/api/auth/refresh', { refresh_token: refresh })
        localStorage.setItem('access_token',  data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        orig.headers.Authorization = `Bearer ${data.access_token}`
        return api(orig)
      } catch {
        localStorage.clear()
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

// ── Auth ──────────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data).then(r => r.data),
  login:    (data) => api.post('/auth/login', data).then(r => r.data),
  me:       ()     => api.get('/auth/me').then(r => r.data),
  refresh:  (token)=> api.post('/auth/refresh', { refresh_token: token }).then(r => r.data),
}

// ── Market ────────────────────────────────────────────────────────
export const marketAPI = {
  summary:    (date) => api.get('/market/summary',    { params: { trade_date: date } }).then(r => r.data),
  latestDate: ()     => api.get('/market/latest-date').then(r => r.data),
  dates:      ()     => api.get('/market/available-dates').then(r => r.data),
}

// ── Stocks ────────────────────────────────────────────────────────
export const stocksAPI = {
  rankings: (params) => api.get('/stocks/rankings', { params }).then(r => r.data),
  heatmap:  (params) => api.get('/stocks/heatmap',  { params }).then(r => r.data),
  history:  (symbol, lookback_days) =>
    api.get(`/stocks/${symbol}/rs-history`, { params: { lookback_days } }).then(r => r.data),
}

// ── Sectors ───────────────────────────────────────────────────────
export const sectorsAPI = {
  rotation: (date)   => api.get('/sectors/rotation', { params: { trade_date: date } }).then(r => r.data),
  stocks:   (name, date) =>
    api.get(`/sectors/${encodeURIComponent(name)}/stocks`, { params: { trade_date: date } }).then(r => r.data),
}

// ── Portfolio ─────────────────────────────────────────────────────
export const portfolioAPI = {
  current:     (date) => api.get('/portfolio/current',     { params: { trade_date: date } }).then(r => r.data),
  performance: ()     => api.get('/portfolio/performance').then(r => r.data),
  preview:     (date) => api.get('/portfolio/preview',     { params: { trade_date: date } }).then(r => r.data),
}

// ── Acceleration ──────────────────────────────────────────────────
export const accelAPI = {
  data: (params) => api.get('/acceleration', { params }).then(r => r.data),
}

// ── Leadership ────────────────────────────────────────────────────
export const leaderAPI = {
  data: (params) => api.get('/leadership', { params }).then(r => r.data),
}

// ── Payments ──────────────────────────────────────────────────────
export const paymentsAPI = {
  createOrder: (plan) => api.post('/payments/create-order', { plan }).then(r => r.data),
  verify:      (data) => api.post('/payments/verify', data).then(r => r.data),
}

export default api
