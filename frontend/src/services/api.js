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

  // ✅ ADD THIS
 summarization: {
    summarizeFile: (formData) =>
      apiClient.post('/summarization/summarize_file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),

    translateAndSummarizeFile: (formData) =>
      apiClient.post('/summarization/translate_and_summarize_file', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }),

    summarizeFromUrl: (data) =>
      apiClient.post('/summarization/summarize_from_url', data),

    translateFromUrl: (data) =>
      apiClient.post('/summarization/translate_from_url', data),
  },
};

export default api;