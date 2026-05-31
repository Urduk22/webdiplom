import axios from 'axios';

const API = axios.create({ baseURL: '/api' });

API.interceptors.request.use((req) => {
    const token = localStorage.getItem('token');
    if (token) {
        req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
});

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

export const getSurveys = () => API.get('/surveys');
export const getSurvey = (id) => API.get(`/surveys/${id}`);
export const getSurveyByPublicId = (publicId) => API.get(`/surveys/public/${publicId}`);
export const createSurvey = (data) => API.post('/surveys', data);
export const deleteSurvey = (id) => API.delete(`/surveys/${id}`);
export const submitResponse = (id, answers) => API.post(`/surveys/${id}/submit`, answers);

export const analyzeSurvey = (id, params) => API.post(`/surveys/${id}/analyze`, params);
export const uploadFile = (formData) => API.post('/analyze', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
});

export const getSurveyStats = (id) => API.get(`/surveys/${id}/stats`);
export const exportSurveyStats = (id) => API.get(`/surveys/${id}/export-stats`, { responseType: 'blob' });
export const downloadFile = (filename) => API.get(`/download/${filename}`, { responseType: 'blob' });

export { API };