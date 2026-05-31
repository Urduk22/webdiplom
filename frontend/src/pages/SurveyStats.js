import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography, Paper, CircularProgress, Alert, Button, Card, CardContent } from '@mui/material';
import { getSurveyStats, exportSurveyStats } from '../services/api';
import Plot from 'react-plotly.js';

export default function SurveyStats() {
    const { id } = useParams();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const fetchStats = async () => {
            try {
                const res = await getSurveyStats(id);
                setStats(res.data);
            } catch (err) {
                setError('Не удалось загрузить статистику');
            } finally {
                setLoading(false);
            }
        };
        fetchStats();
    }, [id]);

    const exportExcel = async () => {
        try {
            const res = await exportSurveyStats(id);
            const url = window.URL.createObjectURL(new Blob([res.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `survey_${id}_stats.xlsx`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (err) {
            alert('Ошибка экспорта');
        }
    };

    if (loading) return <CircularProgress />;
    if (error) return <Alert severity="error">{error}</Alert>;

    return (
        <Box>
            <Typography variant="h4" gutterBottom>Статистика опроса</Typography>
            <Button variant="contained" onClick={exportExcel} sx={{ mb: 2 }}>Экспорт в Excel</Button>
            {stats.map((q, idx) => (
                <Card key={q.id} sx={{ mb: 3 }}>
                    <CardContent>
                        <Typography variant="h6">{idx+1}. {q.text}</Typography>
                        {q.type === 'single' && (
                            <>
                                <Typography variant="body2" color="textSecondary">Всего ответов: {q.total}</Typography>
                                <Plot
                                    data={[{
                                        type: 'pie',
                                        labels: q.data.map(d => d.text),
                                        values: q.data.map(d => d.count),
                                        textinfo: 'label+percent',
                                        hoverinfo: 'label+value+percent',
                                    }]}
                                    layout={{ width: 500, height: 400, title: 'Распределение ответов' }}
                                />
                                <table style={{ width: '100%', marginTop: 10 }}>
                                    <thead><tr><th>Вариант</th><th>Голосов</th><th>Процент</th></tr></thead>
                                    <tbody>
                                        {q.data.map(d => (
                                            <tr key={d.text}><td>{d.text}</td><td>{d.count}</td><td>{d.percent}%</td></tr>
                                        ))}
                                    </tbody>
                                </table>
                            </>
                        )}
                        {q.type === 'multiple' && (
                            <>
                                <Typography variant="body2" color="textSecondary">Всего ответов: {q.total}</Typography>
                                <Plot
                                    data={[{
                                        type: 'bar',
                                        x: q.data.map(d => d.text),
                                        y: q.data.map(d => d.count),
                                        text: q.data.map(d => d.count),
                                        textposition: 'auto',
                                    }]}
                                    layout={{ width: 600, height: 400, title: 'Количество выборов' }}
                                />
                                <table style={{ width: '100%', marginTop: 10 }}>
                                    <thead><tr><th>Вариант</th><th>Выборов</th><th>Процент от опрошенных</th></tr></thead>
                                    <tbody>
                                        {q.data.map(d => (
                                            <tr key={d.text}><td>{d.text}</td><td>{d.count}</td><td>{d.percent}%</td></tr>
                                        ))}
                                    </tbody>
                                </table>
                            </>
                        )}
                        {q.type === 'scale' && (
                            <>
                                <Typography variant="body2">Среднее: {q.mean}, Медиана: {q.median}</Typography>
                                <Plot
                                    data={[{
                                        type: 'bar',
                                        x: q.data.map(d => d.value),
                                        y: q.data.map(d => d.count),
                                    }]}
                                    layout={{ width: 500, height: 400, title: 'Распределение оценок', xaxis: { title: 'Оценка' }, yaxis: { title: 'Количество' } }}
                                />
                            </>
                        )}
                        {q.type === 'text' && (
                            <>
                                <Typography variant="body2">Всего текстовых ответов: {q.total}</Typography>
                                <Box sx={{ maxHeight: 300, overflow: 'auto', bgcolor: '#f5f5f5', p: 1 }}>
                                    {q.answers.map((ans, i) => <div key={i}>— {ans}</div>)}
                                    {q.total > 50 && <div>... и ещё {q.total-50} ответов</div>}
                                </Box>
                            </>
                        )}
                    </CardContent>
                </Card>
            ))}
        </Box>
    );
}