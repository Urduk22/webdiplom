import React, { useState, useEffect } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Container from '@mui/material/Container';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Box from '@mui/material/Box';
import Login from './pages/Login';
import Register from './pages/Register';
import Surveys from './pages/Surveys';
import CreateSurvey from './pages/CreateSurvey';
import TakeSurvey from './pages/TakeSurvey';
import SurveyResults from './pages/SurveyResults';
import UploadAnalysis from './pages/UploadAnalysis';
import { getMe } from './services/api';

const theme = createTheme({
  palette: {
    primary: { main: '#3b82f6' },
    secondary: { main: '#64748b' },
  },
});

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      getMe()
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('token');
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  if (loading) return <div>Загрузка...</div>;

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Анализ опросов
          </Typography>
          {user ? (
            <>
              <Button color="inherit" onClick={() => window.location.href = '/'}>Главная</Button>
              <Button color="inherit" onClick={() => window.location.href = '/surveys'}>Мои опросы</Button>
              <Button color="inherit" onClick={() => window.location.href = '/create-survey'}>Создать</Button>
              <Button color="inherit" onClick={handleLogout}>Выйти ({user.username})</Button>
            </>
          ) : (
            <>
              <Button color="inherit" onClick={() => window.location.href = '/login'}>Вход</Button>
              <Button color="inherit" onClick={() => window.location.href = '/register'}>Регистрация</Button>
            </>
          )}
        </Toolbar>
      </AppBar>
      <Container sx={{ mt: 4 }}>
        <Routes>
          <Route path="/" element={<UploadAnalysis user={user} />} />
          <Route path="/login" element={!user ? <Login /> : <Navigate to="/" />} />
          <Route path="/register" element={!user ? <Register /> : <Navigate to="/" />} />
          <Route path="/surveys" element={user ? <Surveys user={user} /> : <Navigate to="/login" />} />
          <Route path="/create-survey" element={user ? <CreateSurvey /> : <Navigate to="/login" />} />
          <Route path="/surveys/:id" element={<TakeSurvey />} />
          <Route path="/surveys/:id/results" element={user ? <SurveyResults /> : <Navigate to="/login" />} />
        </Routes>
      </Container>
    </ThemeProvider>
  );
}

export default App;