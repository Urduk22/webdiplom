import React, { useState } from 'react';
import { Paper, Typography, Box, Button, TextField, MenuItem, Select, FormControlLabel, Checkbox, Alert, CircularProgress } from '@mui/material';
import { uploadFile, downloadFile } from '../services/api';

export default function UploadAnalysis({ user }) {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const [params, setParams] = useState({
    drop_first: false,
    fill_na_zero: true,
    encode_cat: false,
    max_cat: 10,
    threshold: 0.3,
    n_launches: 10,
    n_solutions: 100,
    cap: 1000,
    frac: 0.35,
    q: 1.0,
    target_column: '',
    method: 'graph',
    top_k: 10
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setError('Выберите файл');
      return;
    }
    setLoading(true);
    setError('');
    const formData = new FormData();
    formData.append('file', file);
    for (let [key, val] of Object.entries(params)) {
      formData.append(key, val);
    }
    try {
      const res = await uploadFile(formData);
      setResults(res.data);
    } catch (err) {
    const data = err.response?.data;
    let errorMsg = 'Ошибка загрузки или анализа';
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
      <Typography variant="h4" gutterBottom>Анализ файла опроса</Typography>
      <Paper sx={{ p: 3 }}>
        <form onSubmit={handleSubmit}>
          <input type="file" accept=".csv,.xls,.xlsx,.ods" onChange={(e) => setFile(e.target.files[0])} required />
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 2 }}>
            <TextField label="Порог" type="number" size="small" value={params.threshold} onChange={(e) => setParams({...params, threshold: parseFloat(e.target.value)})} sx={{ width: 100 }} />
            <TextField label="Запусков" type="number" size="small" value={params.n_launches} onChange={(e) => setParams({...params, n_launches: parseInt(e.target.value)})} sx={{ width: 100 }} />
            <TextField label="Решений" type="number" size="small" value={params.n_solutions} onChange={(e) => setParams({...params, n_solutions: parseInt(e.target.value)})} sx={{ width: 100 }} />
            <TextField label="Cap" type="number" size="small" value={params.cap} onChange={(e) => setParams({...params, cap: parseInt(e.target.value)})} sx={{ width: 100 }} />
            <TextField label="Frac" type="number" size="small" value={params.frac} onChange={(e) => setParams({...params, frac: parseFloat(e.target.value)})} sx={{ width: 100 }} />
            <TextField label="q" type="number" size="small" value={params.q} onChange={(e) => setParams({...params, q: parseFloat(e.target.value)})} sx={{ width: 100 }} />
            <TextField label="Целевой столбец" size="small" value={params.target_column} onChange={(e) => setParams({...params, target_column: e.target.value})} sx={{ width: 150 }} />
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
          <Button variant="contained" type="submit" disabled={loading} sx={{ mt: 2 }}>Запустить анализ</Button>
        </form>
      </Paper>

      {loading && <CircularProgress sx={{ mt: 2 }} />}
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {results && (
        <Paper sx={{ p: 2, mt: 2 }}>
          <Typography variant="h6">Результаты</Typography>
          <Typography>Максимальный вес: {results.w_max}</Typography>
          <Typography>Выбрано столбцов: {results.selected_columns?.length || 0}</Typography>
          <ul>
            {results.selected_columns?.map(col => <li key={col}>{col}</li>)}
          </ul>
          <Box>
            <Button onClick={() => handleDownload(results.correlation_file)}>Скачать корреляцию (CSV)</Button>
            <Button onClick={() => handleDownload(results.algorithm_file)} sx={{ ml: 1 }}>Скачать алгоритм (TXT)</Button>
          </Box>
        </Paper>
      )}
    </Box>
  );
}