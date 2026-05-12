import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8000/api' });

API.interceptors.request.use((req) => {
    const token = localStorage.getItem('token');
    if (token) {
        req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
});

// Регистрация и вход
export const register = (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    return API.post('/register', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
};

export const login = (username, password) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);
    return API.post('/token', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    });
};

export const getMe = () => API.get('/me');

// Опросы
export const getSurveys = () => API.get('/surveys');
export const getSurvey = (id) => API.get(`/surveys/${id}`);
export const createSurvey = (data) => API.post('/surveys', data);
export const deleteSurvey = (id) => API.delete(`/surveys/${id}`);
export const submitResponse = (id, answers) => API.post(`/surveys/${id}/submit`, answers);

// Анализ
export const analyzeSurvey = (id, params) => API.post(`/surveys/${id}/analyze`, params);
export const uploadFile = (formData) => API.post('/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
});

// Статистика и экспорт
export const getSurveyStats = (id) => API.get(`/surveys/${id}/stats`);
export const exportSurveyStats = (id) => API.get(`/surveys/${id}/export-stats`, { responseType: 'blob' });
export const downloadFile = (filename) => API.get(`/download/${filename}`, { responseType: 'blob' });

// Экспорт самого экземпляра API (для прямых запросов, например bulk-submit)
export { API };