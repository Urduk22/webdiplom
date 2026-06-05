import React, { useState } from 'react';
import { TextField, Button, Paper, Typography, Box, Alert } from '@mui/material';
import { register } from '../services/api';

export default function Register() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await register(username, password);
      setSuccess('Регистрация успешна! Перенаправление на вход...');
      setTimeout(() => {
        window.location.href = '/login';
      }, 2000);
    } catch (err) {
      if (err.response && err.response.status === 422) {
        const errors = err.response.data.detail;
        if (Array.isArray(errors)) {
          const messages = errors.map(e => `${e.loc.join('.')}: ${e.msg}`);
          setError(messages.join(', '));
        } else {
          setError('Ошибка валидации данных');
        }
      } else if (err.response && err.response.data && err.response.data.detail) {
        setError(err.response.data.detail);
      } else {
        setError('Ошибка регистрации. Попробуйте позже.');
      }
    }
  };

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
      <Paper sx={{ p: 4, width: 400 }}>
        <Typography variant="h5" gutterBottom>Регистрация</Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
        <form onSubmit={handleSubmit}>
          <TextField
            fullWidth
            label="Имя пользователя"
            margin="normal"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="off"
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            fullWidth
            label="Пароль"
            type="password"
            margin="normal"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="off"
            InputLabelProps={{ shrink: true }}
          />
          <Button fullWidth variant="contained" type="submit" sx={{ mt: 2 }}>
            Зарегистрироваться
          </Button>
        </form>
      </Paper>
    </Box>
  );
}