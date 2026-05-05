import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Layout from './layouts/Layout';
import FullScreenLoader from './components/FullScreenLoader';
import Login from './pages/Login';
import Register from './pages/Register';
import Surveys from './pages/Surveys';
import CreateSurvey from './pages/CreateSurvey';
import TakeSurvey from './pages/TakeSurvey';
import SurveyResults from './pages/SurveyResults';
import SurveyStats from './pages/SurveyStats';
import UploadAnalysis from './pages/UploadAnalysis';
import NotFound from './pages/NotFound';

const theme = createTheme({
    palette: {
        primary: { main: '#3b82f6' },
        secondary: { main: '#64748b' },
    },
});

function AppContent() {
    const { loading } = useAuth();

    if (loading) return <FullScreenLoader open />;

    return (
        <Layout>
            <Routes>
                <Route path="/" element={<UploadAnalysis />} />
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/surveys" element={<ProtectedRoute><Surveys /></ProtectedRoute>} />
                <Route path="/create-survey" element={<ProtectedRoute><CreateSurvey /></ProtectedRoute>} />
                <Route path="/surveys/:id" element={<TakeSurvey />} />
                <Route path="/surveys/:id/results" element={<ProtectedRoute><SurveyResults /></ProtectedRoute>} />
                <Route path="/surveys/:id/stats" element={<ProtectedRoute><SurveyStats /></ProtectedRoute>} />
                <Route path="*" element={<NotFound />} />
            </Routes>
        </Layout>
    );
}

function App() {
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <AuthProvider>
                <AppContent />
            </AuthProvider>
        </ThemeProvider>
    );
}

export default App;