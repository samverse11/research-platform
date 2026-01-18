// frontend/src/services/api.js
import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json'
  }
});

const api = {
  crawler: {
    search: (params) => apiClient.post('/crawler/search', params),
    getSources: () => apiClient.get('/crawler/sources'),
  },
};

export default api;