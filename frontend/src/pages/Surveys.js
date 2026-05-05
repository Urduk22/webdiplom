import React, { useState, useEffect } from 'react';
import {
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Paper, Button, IconButton, Typography, Alert, Box, useMediaQuery, useTheme
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { getSurveys, deleteSurvey } from '../services/api';

export default function Surveys() {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const [surveys, setSurveys] = useState([]);
    const [error, setError] = useState('');

    useEffect(() => {
        loadSurveys();
    }, []);

    const loadSurveys = async () => {
        try {
            const res = await getSurveys();
            setSurveys(res.data);
        } catch (err) {
            setError('Ошибка загрузки опросов');
        }
    };

    const handleDelete = async (id) => {
        if (window.confirm('Удалить опрос?')) {
            await deleteSurvey(id);
            loadSurveys();
        }
    };

    return (
        <>
            <Typography variant="h4" gutterBottom>Мои опросы</Typography>
            {error && <Alert severity="error">{error}</Alert>}
            <Box sx={{ overflowX: 'auto' }}>
                <TableContainer component={Paper}>
                    <Table sx={{ minWidth: 600 }}>
                        <TableHead>
                            <TableRow>
                                <TableCell>Название</TableCell>
                                <TableCell>Описание</TableCell>
                                <TableCell>Дата</TableCell>
                                <TableCell>Действия</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {surveys.map((s) => (
                                <TableRow key={s.id}>
                                    <TableCell>{s.title}</TableCell>
                                    <TableCell>{s.description}</TableCell>
                                    <TableCell>{new Date(s.created_at).toLocaleDateString()}</TableCell>
                                    <TableCell>
                                        <Button href={`/surveys/${s.id}`} variant="outlined" size="small">Пройти</Button>
                                        <Button href={`/surveys/${s.id}/results`} variant="outlined" size="small" sx={{ ml: 1 }}>Анализ</Button>
                                        <Button href={`/surveys/${s.id}/stats`} variant="outlined" size="small" sx={{ ml: 1 }}>Статистика</Button>
                                        <IconButton onClick={() => handleDelete(s.id)} color="error"><DeleteIcon /></IconButton>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Box>
        </>
    );
}