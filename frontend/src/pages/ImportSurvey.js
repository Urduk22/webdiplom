import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box, Typography, Paper, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    TextField, MenuItem, Select, FormControl, InputLabel, Alert, CircularProgress, FormControlLabel, Checkbox
} from '@mui/material';
import FileUploadButton from '../components/FileUploadButton';
import { createSurvey, getSurvey, API } from '../services/api';
import axios from 'axios';
import Papa from 'papaparse';

export default function ImportSurvey() {
    const navigate = useNavigate();
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [rawData, setRawData] = useState(null);
    const [questions, setQuestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [autoDetectOptions, setAutoDetectOptions] = useState(true);
    const [importResponsesFlag, setImportResponsesFlag] = useState(true);

    const handleFileSelect = (selectedFile) => {
        setFile(selectedFile);
        setError('');
        Papa.parse(selectedFile, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
                const headers = results.meta.fields;
                if (!headers || headers.length === 0) {
                    setError('Файл не содержит заголовков');
                    return;
                }
                const sampleRows = results.data.slice(0, 5);
                setPreview(sampleRows);
                setRawData(results.data);

                const initQuestions = headers.map((header, idx) => {
                    let detectedType = 'text';
                    let detectedOptions = [];

                    if (autoDetectOptions) {
                        const allValues = results.data.map(row => row[header]).filter(v => v && v.trim());
                        if (allValues.length > 0) {
                            const hasDelimiters = allValues.some(v => v.includes(',') || v.includes(';') || v.includes('|'));
                            if (hasDelimiters) {
                                detectedType = 'multiple';
                                const allOpts = new Set();
                                allValues.forEach(v => {
                                    const parts = v.split(/[,;|]/).map(p => p.trim()).filter(p => p);
                                    parts.forEach(p => allOpts.add(p));
                                });
                                detectedOptions = Array.from(allOpts);
                            } else {
                                const uniqueVals = [...new Set(allValues)];
                                if (uniqueVals.length <= 10 && uniqueVals.length > 1) {
                                    detectedType = 'single';
                                    detectedOptions = uniqueVals;
                                } else if (uniqueVals.length > 10 && allValues.every(v => !isNaN(parseFloat(v)))) {
                                    detectedType = 'scale';
                                } else {
                                    detectedType = 'text';
                                }
                            }
                        }
                    }

                    return {
                        originalName: header,
                        text: header,
                        type: detectedType,
                        order: idx,
                        options: detectedOptions,
                        scale_min: 1,
                        scale_max: 10
                    };
                });
                setQuestions(initQuestions);
            },
            error: (err) => setError('Ошибка парсинга CSV: ' + err.message)
        });
    };

    const handleQuestionChange = (index, field, value) => {
        const updated = [...questions];
        updated[index][field] = value;
        if (field === 'type' && value !== 'single' && value !== 'multiple') {
            updated[index].options = [];
        }
        setQuestions(updated);
    };

    const handleOptionsChange = (index, optionsStr) => {
        const options = optionsStr.split(',').map(s => s.trim()).filter(s => s);
        const updated = [...questions];
        updated[index].options = options;
        setQuestions(updated);
    };

    const handleCreateSurvey = async () => {
        if (!questions.length) return;
        setLoading(true);
        try {
            // 1. Создаём опрос
            const payload = {
                title: 'Импортированный опрос',
                description: '',
                questions: questions.map(q => ({
                    text: q.text,
                    question_type: q.type,
                    order: q.order,
                    options: q.options,
                    scale_min: q.scale_min,
                    scale_max: q.scale_max
                }))
            };
            const createRes = await createSurvey(payload);
            const surveyId = createRes.data.id;

            // 2. Если нужно импортировать ответы и есть данные
            if (importResponsesFlag && rawData && rawData.length) {
                // Получаем актуальные id вопросов после создания на сервере
                const survey = await getSurvey(surveyId);
                const qIdMap = {};
                survey.questions.forEach((q, idx) => {
                    qIdMap[questions[idx].originalName] = q.id;
                });

                const allResponses = [];
                for (const row of rawData) {
                    const answers = {};
                    for (let i = 0; i < questions.length; i++) {
                        const q = questions[i];
                        const rawValue = row[q.originalName] || '';
                        let processedValue = null;
                        const qId = qIdMap[q.originalName];
                        if (!qId) continue;

                        if (q.type === 'multiple') {
                            const parts = rawValue.split(/[,;|]/).map(p => p.trim()).filter(p => p);
                            const optionIds = parts.map(part => {
                                const optIndex = q.options.findIndex(opt => opt === part);
                                return optIndex !== -1 ? optIndex + 1 : null;
                            }).filter(id => id !== null);
                            processedValue = optionIds;
                        } else if (q.type === 'single') {
                            const optIndex = q.options.findIndex(opt => opt === rawValue);
                            processedValue = optIndex !== -1 ? optIndex + 1 : null;
                        } else if (q.type === 'scale') {
                            const num = parseFloat(rawValue);
                            processedValue = isNaN(num) ? null : num;
                        } else {
                            processedValue = rawValue;
                        }
                        if (processedValue !== null) {
                            answers[qId] = processedValue;
                        }
                    }
                    if (Object.keys(answers).length) {
                        allResponses.push(answers);
                    }
                }

                // Отправляем одним запросом
                const token = localStorage.getItem('token');
                await axios.post(
                    `http://localhost:8000/api/surveys/${surveyId}/bulk-submit`,
                    allResponses,
                    {
                        headers: { Authorization: `Bearer ${token}` }
                    }
                );
            }

            navigate(`/surveys/${surveyId}`);
        } catch (err) {
            console.error(err);
            setError('Ошибка создания опроса или импорта ответов');
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box>
            <Typography variant="h4" gutterBottom>Импорт опроса из CSV (Google Forms)</Typography>
            <Paper sx={{ p: 3 }}>
                <FileUploadButton accept=".csv" onFileSelect={handleFileSelect}>
                    Выберите CSV файл
                </FileUploadButton>
                {file && <Typography sx={{ mt: 1 }}>Выбран: {file.name}</Typography>}

                <Box sx={{ mt: 2 }}>
                    <FormControlLabel
                        control={<Checkbox checked={autoDetectOptions} onChange={(e) => setAutoDetectOptions(e.target.checked)} />}
                        label="Автоматически определять варианты для одиночного/множественного выбора (по данным)"
                    />
                    <FormControlLabel
                        control={<Checkbox checked={importResponsesFlag} onChange={(e) => setImportResponsesFlag(e.target.checked)} />}
                        label="Импортировать ответы из CSV в базу данных"
                    />
                </Box>

                {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

                {preview && (
                    <>
                        <Typography variant="h6" sx={{ mt: 3 }}>Предпросмотр данных</Typography>
                        <TableContainer component={Paper} sx={{ mt: 1, maxHeight: 300 }}>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        {questions.map((q, idx) => <TableCell key={idx}>{q.originalName}</TableCell>)}
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {preview.map((row, i) => (
                                        <TableRow key={i}>
                                            {questions.map((q, j) => <TableCell key={j}>{row[q.originalName]}</TableCell>)}
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>

                        <Typography variant="h6" sx={{ mt: 3 }}>Настройка вопросов</Typography>
                        {questions.map((q, idx) => (
                            <Paper key={idx} sx={{ p: 2, mt: 2 }}>
                                <TextField
                                    label="Текст вопроса"
                                    fullWidth
                                    value={q.text}
                                    onChange={(e) => handleQuestionChange(idx, 'text', e.target.value)}
                                    sx={{ mb: 2 }}
                                />
                                <FormControl fullWidth sx={{ mb: 2 }}>
                                    <InputLabel>Тип вопроса</InputLabel>
                                    <Select value={q.type} onChange={(e) => handleQuestionChange(idx, 'type', e.target.value)}>
                                        <MenuItem value="text">Текстовый</MenuItem>
                                        <MenuItem value="single">Одиночный выбор</MenuItem>
                                        <MenuItem value="multiple">Множественный выбор</MenuItem>
                                        <MenuItem value="scale">Числовая шкала</MenuItem>
                                    </Select>
                                </FormControl>
                                {(q.type === 'single' || q.type === 'multiple') && (
                                    <TextField
                                        label="Варианты ответа (через запятую)"
                                        fullWidth
                                        defaultValue={q.options.join(', ')}
                                        onChange={(e) => handleOptionsChange(idx, e.target.value)}
                                        helperText="Например: Да, Нет, Возможно"
                                    />
                                )}
                                {q.type === 'scale' && (
                                    <Box sx={{ display: 'flex', gap: 2 }}>
                                        <TextField type="number" label="Min" value={q.scale_min} onChange={(e) => handleQuestionChange(idx, 'scale_min', parseInt(e.target.value))} />
                                        <TextField type="number" label="Max" value={q.scale_max} onChange={(e) => handleQuestionChange(idx, 'scale_max', parseInt(e.target.value))} />
                                    </Box>
                                )}
                            </Paper>
                        ))}
                        <Button variant="contained" onClick={handleCreateSurvey} disabled={loading} sx={{ mt: 3 }}>
                            {loading ? <CircularProgress size={24} /> : 'Создать опрос и импортировать ответы'}
                        </Button>
                    </>
                )}
            </Paper>
        </Box>
    );
}