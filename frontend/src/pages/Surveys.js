import React, { useState, useEffect } from 'react';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Button, IconButton, Typography, Alert } from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { getSurveys, deleteSurvey } from '../services/api';

export default function Surveys({ user }) {
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
    const data = err.response?.data;
    let errorMsg = 'Ошибка загрузки опросов';
    if (data) {
        if (typeof data === 'string') errorMsg = data;
        else if (data.detail) errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        else if (data.message) errorMsg = data.message;
        else errorMsg = JSON.stringify(data);
    }
    setError(errorMsg);
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
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Название</TableCell>
              <TableCell>Описание</TableCell>
              <TableCell>Дата</TableCell>
              <TableCell>Действия</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {surveys.map(s => (
              <TableRow key={s.id}>
                <TableCell>{s.title}</TableCell>
                <TableCell>{s.description}</TableCell>
                <TableCell>{new Date(s.created_at).toLocaleDateString()}</TableCell>
                <TableCell>
                  <Button href={`/surveys/${s.id}`} variant="outlined" size="small">Пройти</Button>
                  <Button href={`/surveys/${s.id}/results`} variant="outlined" size="small" sx={{ ml: 1 }}>Результаты</Button>
                  <IconButton onClick={() => handleDelete(s.id)} color="error"><DeleteIcon /></IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </>
  );
}