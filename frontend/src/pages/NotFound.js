import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { Link } from 'react-router-dom';

export default function NotFound() {
    return (
        <Box sx={{ textAlign: 'center', mt: 8 }}>
            <Typography variant="h1" color="primary" sx={{ fontSize: '6rem', fontWeight: 'bold' }}>404</Typography>
            <Typography variant="h5" gutterBottom>Страница не найдена</Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
                Возможно, вы перешли по неверной ссылке или страница была удалена.
            </Typography>
            <Button component={Link} to="/" variant="contained">Вернуться на главную</Button>
        </Box>
    );
}