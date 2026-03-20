import axios from 'axios';

const API_BASE_URL = '/api';

const api = axios.create({ baseURL: API_BASE_URL });

// Request interceptor: attach Authorization header
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: auto-refresh on 401
let isRefreshing = false;
let failedQueue: Array<{ resolve: Function; reject: Function }> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) prom.reject(error);
    else prom.resolve(token);
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }
      originalRequest._retry = true;
      isRefreshing = true;
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('No refresh token');
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        processQueue(null, data.access_token);
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);


// Auth API functions
export const authApi = {
  login: (email: string, password: string) => api.post('/auth/login', { email, password }),
  register: (email: string, password: string, enterprise_code: string) => api.post('/auth/register', { email, password, enterprise_code }),
  refresh: (refresh_token: string) => api.post('/auth/refresh', { refresh_token }),
};

// User management API functions
export const userApi = {
  listUsers: (params: { page?: number; size?: number; search?: string }) => api.get('/users', { params }),
  createUser: (data: { email: string; password: string; role?: string }) => api.post('/users', data),
  updateUser: (userId: string, data: { role?: string; is_active?: boolean }) => api.put(`/users/${userId}`, data),
  deleteUser: (userId: string) => api.delete(`/users/${userId}`),
  batchImport: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/users/batch-import', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
  },
};

export default api;
