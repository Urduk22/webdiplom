import React, { useState } from 'react';
import { useParams } from 'react-router-dom';
import { Paper, Typography, Box, Button, TextField, MenuItem, Select, FormControlLabel, Checkbox, CircularProgress, Alert } from '@mui/material';
import { analyzeSurvey, downloadFile } from '../services/api';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';

export default function SurveyResults() {
    const { id } = useParams();
    const [results, setResults] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const resultsRef = React.useRef(null);
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
            setError('Ошибка анализа');
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
            document.body.removeChild(link);
        });
    };

    const exportToPDF = async () => {
        if (!resultsRef.current) return;
        try {
            const canvas = await html2canvas(resultsRef.current, { scale: 2 });
            const imgData = canvas.toDataURL('image/png');
            const pdf = new jsPDF('p', 'mm', 'a4');
            const imgWidth = 190;
            const imgHeight = (canvas.height * imgWidth) / canvas.width;
            pdf.addImage(imgData, 'PNG', 10, 0, imgWidth, imgHeight);
            pdf.save('analysis_results.pdf');
        } catch (err) {
            alert('Ошибка генерации PDF');
        }
    };

    return (
        <Box>
            <Typography variant="h4" gutterBottom>Анализ опроса</Typography>
            <Paper sx={{ p: 2, mb: 2 }}>
                <Typography variant="h6">Настройки анализа</Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: 1 }}>
                    {/* все поля аналогично UploadAnalysis */}
                    <TextField label="Порог" type="number" size="small" value={params.threshold} onChange={(e) => setParams({...params, threshold: parseFloat(e.target.value)})} sx={{ width: 100 }} />
                    <TextField label="Запусков" type="number" size="small" value={params.n_launches} onChange={(e) => setParams({...params, n_launches: parseInt(e.target.value)})} sx={{ width: 100 }} />
                    <TextField label="Решений" type="number" size="small" value={params.n_solutions} onChange={(e) => setParams({...params, n_solutions: parseInt(e.target.value)})} sx={{ width: 100 }} />
                    <TextField label="Cap" type="number" size="small" value={params.cap} onChange={(e) => setParams({...params, cap: parseInt(e.target.value)})} sx={{ width: 100 }} />
                    <TextField label="Frac" type="number" size="small" value={params.frac} onChange={(e) => setParams({...params, frac: parseFloat(e.target.value)})} sx={{ width: 100 }} />
                    <TextField label="q" type="number" size="small" value={params.q} onChange={(e) => setParams({...params, q: parseFloat(e.target.value)})} sx={{ width: 100 }} />
                    <TextField label="Целевой столбец (№)" type="number" size="small" value={params.target_column} onChange={(e) => setParams({...params, target_column: e.target.value})} sx={{ width: 150 }} />
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
                <Button variant="contained" onClick={handleAnalyze} disabled={loading} sx={{ mt: 2 }}>
                    {loading ? <CircularProgress size={24} /> : 'Запустить анализ'}
                </Button>
            </Paper>

            {error && <Alert severity="error">{error}</Alert>}

            {results && (
                <Paper sx={{ p: 2, mt: 2 }} ref={resultsRef}>
                    <Typography variant="h6">Результаты</Typography>
                    <Typography>Максимальный вес: {results.w_max}</Typography>
                    <Typography>Выбрано столбцов: {results.selected_columns?.length || 0}</Typography>
                    <ul>{results.selected_columns?.map(col => <li key={col}>{col}</li>)}</ul>
                    <Box sx={{ mt: 2 }}>
                        <Button onClick={() => handleDownload(results.correlation_file)}>Скачать корреляцию (CSV)</Button>
                        <Button onClick={() => handleDownload(results.algorithm_file)} sx={{ ml: 1 }}>Скачать алгоритм (TXT)</Button>
                        <Button variant="outlined" onClick={exportToPDF} sx={{ ml: 1 }}>Экспорт в PDF</Button>
                    </Box>
                </Paper>
            )}
        </Box>
    );
}