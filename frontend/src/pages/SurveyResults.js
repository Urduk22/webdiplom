import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Paper, Typography, Box, Button, TextField, MenuItem, Select, FormControlLabel, Checkbox, CircularProgress, Alert } from '@mui/material';
import { analyzeSurvey, downloadFile } from '../services/api';

export default function SurveyResults() {
  const { id } = useParams();
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [params, setParams] = useState({
    threshold: 0.3,
    n_launches: 10,
    n_solutions: 100,
    cap: 1000,
    frac: 0.35,
    q: 1.0,
    drop_first: false,
    fill_na_zero: true,
    encode_cat: true,
    max_cat: 10,
    target_column: '',
    method: 'graph',
    top_k: 10
  });

  const handleAnalyze = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await analyzeSurvey(id, params);
      setResults(res.data);
    } catch (err) {
    const data = err.response?.data;
    let errorMsg = 'Ошибка анализа';
    if (data) {
        if (typeof data === 'string') errorMsg = data;
        else if (data.detail) errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        else if (data.message) errorMsg = data.message;
        else errorMsg = JSON.stringify(data);
    }
    setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = (filename) => {
    downloadFile(filename).then(res => {
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
    });
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Анализ опроса</Typography>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="h6">Настройки анализа</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
          <TextField label="Порог" type="number" size="small" value={params.threshold} onChange={(e) => setParams({...params, threshold: parseFloat(e.target.value)})} sx={{ width: 100 }} />
          <TextField label="Запусков" type="number" size="small" value={params.n_launches} onChange={(e) => setParams({...params, n_launches: parseInt(e.target.value)})} sx={{ width: 100 }} />
          <TextField label="Решений" type="number" size="small" value={params.n_solutions} onChange={(e) => setParams({...params, n_solutions: parseInt(e.target.value)})} sx={{ width: 100 }} />
          <TextField label="Cap" type="number" size="small" value={params.cap} onChange={(e) => setParams({...params, cap: parseInt(e.target.value)})} sx={{ width: 100 }} />
          <TextField label="Frac" type="number" size="small" value={params.frac} onChange={(e) => setParams({...params, frac: parseFloat(e.target.value)})} sx={{ width: 100 }} />
          <TextField label="q" type="number" size="small" value={params.q} onChange={(e) => setParams({...params, q: parseFloat(e.target.value)})} sx={{ width: 100 }} />
          <TextField label="Целевой столбец (номер)"
    type="number"
    size="small"
    value={params.target_column}
    onChange={(e) => setParams({...params, target_column: e.target.value})}
    sx={{ width: 150 }}
    InputLabelProps={{ shrink: true }}
            />
          <Select size="small" value={params.method} onChange={(e) => setParams({...params, method: e.target.value})} sx={{ width: 120 }}>

            <MenuItem value="graph">Графовый</MenuItem>
            <MenuItem value="correlation">Корреляция</MenuItem>
            <MenuItem value="anova">ANOVA</MenuItem>
            <MenuItem value="pca">PCA</MenuItem>
          </Select>
          <TextField label="Top K" type="number" size="small" value={params.top_k} onChange={(e) => setParams({...params, top_k: parseInt(e.target.value)})} sx={{ width: 80 }} />
        </Box>
        <Box sx={{ mt: 1 }}>
          <FormControlLabel control={<Checkbox checked={params.drop_first} onChange={(e) => setParams({...params, drop_first: e.target.checked})} />} label="Удалить первый столбец" />
          <FormControlLabel control={<Checkbox checked={params.fill_na_zero} onChange={(e) => setParams({...params, fill_na_zero: e.target.checked})} />} label="Замена пустых на 0" />
          <FormControlLabel control={<Checkbox checked={params.encode_cat} onChange={(e) => setParams({...params, encode_cat: e.target.checked})} />} label="One-Hot кодирование" />
          <TextField label="Макс. категорий" type="number" size="small" value={params.max_cat} onChange={(e) => setParams({...params, max_cat: parseInt(e.target.value)})} sx={{ width: 100, ml: 2 }} />
        </Box>
        <Button variant="contained" onClick={handleAnalyze} disabled={loading} sx={{ mt: 2 }}>Запустить анализ</Button>
      </Paper>

      {loading && <CircularProgress />}
      {error && <Alert severity="error">{error}</Alert>}
      {results && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6">Выбранные столбцы</Typography>
          <ul>
            {results.selected_columns.map(col => <li key={col}>{col}</li>)}
          </ul>
          <Typography>Максимальный вес: {results.w_max}</Typography>
          <Typography>Количество выбранных: {results.selected_columns.length}</Typography>
          <Box sx={{ mt: 2 }}>
            <Button onClick={() => handleDownload(results.correlation_file)}>Скачать корреляцию (CSV)</Button>
            <Button onClick={() => handleDownload(results.algorithm_file)} sx={{ ml: 1 }}>Скачать алгоритм (TXT)</Button>
          </Box>
        </Paper>
      )}
    </Box>
  );
}