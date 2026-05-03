import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 300000,
});

// ── Attach JWT token to every request if available ──
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('rp_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Handle 401 Unauthorized globally ──
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token and user data
      localStorage.removeItem('rp_token');
      localStorage.removeItem('rp_user');
      
      // Dispatch a custom event so the React app can show a toast
      window.dispatchEvent(new CustomEvent('session-expired'));
    }
    return Promise.reject(error);
  }
);

const api = {
  // ── Auth ──────────────────────────────────────────────
  auth: {
    register: (data) => apiClient.post('/auth/register', data),
    login:    (data) => apiClient.post('/auth/login', data),
    profile:  ()     => apiClient.get('/auth/profile'),
    updateProfile: (data) => apiClient.put('/auth/profile', data),
  },

  // ── History / Dashboard ──────────────────────────────
  history: {
    dashboardStats: ()          => apiClient.get('/history/dashboard/stats'),
    getSummaries:   (skip = 0)  => apiClient.get(`/history/summaries?skip=${skip}&limit=50`),
    getSummary:     (id)        => apiClient.get(`/history/summaries/${id}`),
    deleteSummary:  (id)        => apiClient.delete(`/history/summaries/${id}`),
    downloadSummary:(id)        => apiClient.get(`/history/summaries/${id}/download`, { responseType: 'text' }),
    getSearches:    (skip = 0)  => apiClient.get(`/history/searches?skip=${skip}&limit=50`),
    deleteSearch:   (id)        => apiClient.delete(`/history/searches/${id}`),
    getUploads:     (skip = 0)  => apiClient.get(`/history/uploads?skip=${skip}&limit=50`),
    deleteUpload:   (id)        => apiClient.delete(`/history/uploads/${id}`),
  },

  // ── Crawler ──────────────────────────────────────────
  crawler: {
    search: (params) => apiClient.post('/crawler/search', params),
    getSources: () => apiClient.get('/crawler/sources'),
  },

  // ── Analyzer ─────────────────────────────────────────
  analyzer: {
    submit: (formData) =>
      apiClient.post('/analyzer/analyze/submit', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      }),
    status: (jobId) => apiClient.get(`/analyzer/analyze/status/${jobId}`),
    deleteJob: (jobId) => apiClient.delete(`/analyzer/analyze/job/${jobId}`),
    health: () => apiClient.get('/analyzer/health'),
  },

  // ── Summarization ────────────────────────────────────
  summarization: {
    summarizeFile: (formData) =>
      apiClient.post('/summarization/summarize_file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 0,
      }),

    translateAndSummarizeFile: (formData) =>
      apiClient.post('/summarization/translate_and_summarize_file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 0,
      }),

    summarizeFromUrl: (data) =>
      apiClient.post('/summarization/summarize_from_url', data),

    translateFromUrl: (data) =>
      apiClient.post('/summarization/translate_from_url', data),
  },
};

export default api;