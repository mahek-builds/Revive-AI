import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:5000/api/v2',
  headers: {
    'X-API-Key': 'track03_dev_key',
    'Content-Type': 'application/json',
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default api;
