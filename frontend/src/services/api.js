import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8000/api' });

API.interceptors.request.use((req) => {
    const token = localStorage.getItem('token');
    if (token) {
        req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
});

// Регистрация (form-urlencoded)
export const register = (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);
  return API.post('/register', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });
};

// Вход (form-urlencoded)
export const login = (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    return API.post('/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
};
export const exportSurveyStats = (id) => API.get(`/surveys/${id}/export-stats`, { responseType: 'blob' });
export const getSurveyStats = (id) => API.get(`/surveys/${id}/stats`);
export const getMe = () => API.get('/me');
export const getSurveys = () => API.get('/surveys');
export const deleteSurvey = (id) => API.delete(`/surveys/${id}`);
export const createSurvey = (data) => API.post('/surveys', data);
export const getSurvey = (id) => API.get(`/surveys/${id}`);
export const submitResponse = (id, answers) => API.post(`/surveys/${id}/submit`, answers);
export const analyzeSurvey = (id, params) => API.post(`/surveys/${id}/analyze`, params);
export const uploadFile = (formData) => API.post('/analyze', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
export const downloadFile = (filename) => API.get(`/download/${filename}`, { responseType: 'blob' });