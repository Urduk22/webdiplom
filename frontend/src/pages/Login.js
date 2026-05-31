import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextField, Button, Paper, Typography, Box, Alert } from '@mui/material';
import { login, getMe } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function Login() {
    const navigate = useNavigate();
    const { login: authLogin } = useAuth();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const res = await login(username, password);
            const { access_token } = res.data;
            localStorage.setItem('token', access_token);
            const userRes = await getMe();
            authLogin(access_token, userRes.data);
            navigate('/');
        } catch (err) {
            console.error(err);
            setError('Неверное имя пользователя или пароль');
        }
    };

    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
            <Paper sx={{ p: 4, width: 400 }}>
                <Typography variant="h5" gutterBottom>Вход</Typography>
                {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
                <form onSubmit={handleSubmit}>
                    <TextField
                        fullWidth
                        label="Имя пользователя"
                        margin="normal"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                        autoComplete="username"
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
                        autoComplete="current-password"
                        InputLabelProps={{ shrink: true }}
                    />
                    <Button fullWidth variant="contained" type="submit" sx={{ mt: 2 }}>
                        Войти
                    </Button>
                </form>
            </Paper>
        </Box>
    );
}