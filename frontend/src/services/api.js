import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 300000,
});

const api = {
  crawler: {
    search: (params) => apiClient.post('/crawler/search', params),
    getSources: () => apiClient.get('/crawler/sources'),
  },

  // ADD THIS BLOCK
  analyzer: {
    submit:    (formData) => apiClient.post('/analyzer/analyze/submit', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    }),
    status:    (jobId) => apiClient.get(`/analyzer/analyze/status/${jobId}`),
    deleteJob: (jobId) => apiClient.delete(`/analyzer/analyze/job/${jobId}`),
    health:    () => apiClient.get('/analyzer/health'),
  },
};

export default api;