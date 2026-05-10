import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器 - 添加JWT Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 响应拦截器 - 统一错误处理
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || error.message || '请求失败';
    console.error('API Error:', message);
    return Promise.reject(error);
  }
);

export default api;

// 评测相关 API
export const evaluationApi = {
  start: (data) => api.post('/evaluation/start', data),
  list: (params) => api.get('/evaluations', { params }),
  detail: (id) => api.get(`/evaluation/${id}`),
  cancel: (id) => api.post(`/evaluation/${id}/cancel`),
  resume: (id) => api.post(`/evaluation/${id}/resume`),
};

// Agent 相关 API
export const agentApi = {
  list: () => api.get('/agents'),
  detail: (id) => api.get(`/agents/${id}`),
  register: (data) => api.post('/agents/register', data),
  delete: (id) => api.delete(`/agents/${id}`),
};

// 报告相关 API
export const reportApi = {
  list: (params) => api.get('/reports', { params }),
  detail: (id) => api.get(`/reports/${id}`),
  generate: (data) => api.post('/reports/generate', data),
};

// 系统相关 API
export const systemApi = {
  health: () => api.get('/health'),
  ready: () => api.get('/ready'),
  live: () => api.get('/live'),
  info: () => api.get('/info'),
};

// WebSocket 基础URL辅助函数
export const getWsUrl = (path) => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
};

// Agent对比 API
export const comparisonApi = {
  compare: (data) => api.post('/evaluation/compare', data),
  batch: (data) => api.post('/evaluation/batch', data),
};

// 行业基准对比 API
export const benchmarkApi = {
  compare: (data) => api.post('/benchmark', data),
};

// 合规认证 API
export const complianceApi = {
  generate: (data) => api.post('/compliance/report', data),
};

// 智能改进建议 API
export const improvementApi = {
  suggestions: (data) => api.post('/improvement/suggestions', data),
};
