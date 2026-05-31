import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Box, Typography, Paper, Button, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    TextField, MenuItem, Select, FormControl, InputLabel, Alert, CircularProgress, FormControlLabel, Checkbox,
    RadioGroup, Radio, Collapse
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import FileUploadButton from '../components/FileUploadButton';
import { createSurvey, getSurvey, getSurveys } from '../services/api';
import axios from 'axios';
import Papa from 'papaparse';

export default function ImportSurvey() {
    const navigate = useNavigate();
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState(null);
    const [rawData, setRawData] = useState(null);
    const [questions, setQuestions] = useState([]);
    const [loading, setLoading] = useState(false);
    const [parsing, setParsing] = useState(false);
    const [error, setError] = useState('');
    const [autoDetectOptions, setAutoDetectOptions] = useState(true);
    const [importResponsesFlag, setImportResponsesFlag] = useState(true);
    const [importMode, setImportMode] = useState('new');
    const [existingSurveys, setExistingSurveys] = useState([]);
    const [existingSurveyId, setExistingSurveyId] = useState('');
    const [title, setTitle] = useState('');
    const [description, setDescription] = useState('');
    const [showAllQuestions, setShowAllQuestions] = useState(false);

    useEffect(() => {
        if (importMode === 'existing') {
            const fetchSurveys = async () => {
                try {
                    const res = await getSurveys();
                    setExistingSurveys(res.data || []);
                    if (res.data && res.data.length > 0) setExistingSurveyId(res.data[0].id.toString());
                } catch (err) {
                    console.error('Не удалось загрузить опросы', err);
                }
            };
            fetchSurveys();
        }
    }, [importMode]);

    const handleFileSelect = (selectedFile) => {
        setFile(selectedFile);
        setError('');
        setQuestions([]);
        setPreview(null);
        setRawData(null);
        setParsing(true);
        Papa.parse(selectedFile, {
            header: true,
            skipEmptyLines: true,
            complete: (results) => {
                const headers = results.meta.fields;
                if (!headers || headers.length === 0) {
                    setError('Файл не содержит заголовков');
                    setParsing(false);
                    return;
                }
                const sampleRows = results.data.slice(0, 10);
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
                setParsing(false);
            },
            error: (err) => {
                setError('Ошибка парсинга CSV: ' + err.message);
                setParsing(false);
            }
        });
    };

    const handleQuestionChange = (index, field, value) => {
        setQuestions(prev => {
            const updated = [...prev];
            updated[index][field] = value;
            if (field === 'type' && value !== 'single' && value !== 'multiple') {
                updated[index].options = [];
            }
            return updated;
        });
    };

    const handleOptionsChange = (index, optionsStr) => {
        const options = optionsStr.split(',').map(s => s.trim()).filter(s => s);
        setQuestions(prev => {
            const updated = [...prev];
            updated[index].options = options;
            return updated;
        });
    };

    const handleCreateSurvey = async () => {
        if (!questions.length) {
            setError('Нет данных для импорта');
            return;
        }
        setLoading(true);
        try {
            let surveyId;
            if (importMode === 'new') {
                const payload = {
                    title: title.trim() || 'Импортированный опрос',
                    description: description.trim() || '',
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
                surveyId = createRes.data.id;
                console.log('[Import] Создан новый опрос, id:', surveyId);
            } else {
                if (!existingSurveyId) {
                    setError('Выберите существующий опрос');
                    setLoading(false);
                    return;
                }
                surveyId = parseInt(existingSurveyId);
                console.log('[Import] Будем добавлять ответы в существующий опрос id:', surveyId);
            }

            if (importResponsesFlag && rawData && rawData.length) {
                const surveyResponse = await getSurvey(surveyId);
                const survey = surveyResponse.data;

                if (!survey.questions || survey.questions.length === 0) {
                    setError('В выбранном опросе нет вопросов');
                    setLoading(false);
                    return;
                }

                const qMap = new Map();
                survey.questions.forEach(q => {
                    qMap.set(q.text.trim(), q.id);
                });

                const optionMaps = {};
                survey.questions.forEach(q => {
                    const opts = q.options || [];
                    const map = {};
                    opts.forEach(opt => {
                        map[opt.text.trim()] = opt.id;
                    });
                    optionMaps[q.id] = map;
                });

                const allResponses = [];
                for (const row of rawData) {
                    const answers = {};
                    for (let i = 0; i < questions.length; i++) {
                        const q = questions[i];
                        const rawValue = (row[q.originalName] || '').toString().trim();
                        if (!rawValue) continue;
                        let processedValue = null;
                        const qId = qMap.get(q.text);
                        if (!qId) continue;

                        if (q.type === 'multiple') {
                            const parts = rawValue.split(/[,;|]/).map(p => p.trim()).filter(p => p);
                            const optionIds = [];
                            for (const part of parts) {
                                if (optionMaps[qId] && optionMaps[qId][part]) {
                                    optionIds.push(optionMaps[qId][part]);
                                } else {
                                    // fallback: по индексу в q.options (если опрос новый)
                                    const optIndex = q.options.findIndex(opt => opt === part);
                                    if (optIndex !== -1) optionIds.push(optIndex + 1);
                                }
                            }
                            if (optionIds.length) processedValue = optionIds;
                        } else if (q.type === 'single') {
                            if (optionMaps[qId] && optionMaps[qId][rawValue]) {
                                processedValue = optionMaps[qId][rawValue];
                            } else {
                                const optIndex = q.options.findIndex(opt => opt === rawValue);
                                if (optIndex !== -1) processedValue = optIndex + 1;
                            }
                        } else if (q.type === 'scale') {
                            const num = parseFloat(rawValue);
                            if (!isNaN(num)) processedValue = num;
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

                if (allResponses.length) {
                    const token = localStorage.getItem('token');
                    await axios.post(
                        `http://localhost:8000/api/surveys/${surveyId}/bulk-submit`,
                        allResponses,
                        { headers: { Authorization: `Bearer ${token}` } }
                    );
                    console.log(`[Import] Импортировано ${allResponses.length} ответов`);
                } else {
                    setError('Не найдено подходящих ответов для импорта');
                    setLoading(false);
                    return;
                }
            }
            navigate(`/surveys/${surveyId}`);
        } catch (err) {
            console.error('[Import] Ошибка:', err.response?.data || err.message);
            setError(`Ошибка: ${err.response?.data?.detail || err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const visibleQuestions = showAllQuestions ? questions : questions.slice(0, 20);

    return (
        <Box>
            <Typography variant="h4" gutterBottom>Импорт опроса из CSV (Google Forms)</Typography>
            <Paper sx={{ p: 3 }}>
                <FileUploadButton accept=".csv" onFileSelect={handleFileSelect}>
                    Выберите CSV файл
                </FileUploadButton>
                {file && <Typography sx={{ mt: 1 }}>Выбран: {file.name}</Typography>}
                {parsing && <CircularProgress size={24} sx={{ mt: 2 }} />}

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

                <Box sx={{ mt: 2 }}>
                    <Typography variant="body2" gutterBottom>Режим импорта:</Typography>
                    <RadioGroup row value={importMode} onChange={(e) => setImportMode(e.target.value)}>
                        <FormControlLabel value="new" control={<Radio />} label="Создать новый опрос" />
                        <FormControlLabel value="existing" control={<Radio />} label="Добавить ответы в существующий" />
                    </RadioGroup>
                </Box>

                {importMode === 'new' && (
                    <Box sx={{ mt: 2 }}>
                        <TextField
                            fullWidth
                            label="Название опроса"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            margin="normal"
                        />
                        <TextField
                            fullWidth
                            label="Описание (необязательно)"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            margin="normal"
                            multiline
                            rows={2}
                        />
                    </Box>
                )}

                {importMode === 'existing' && (
                    <FormControl fullWidth sx={{ mt: 2 }}>
                        <InputLabel>Выберите опрос</InputLabel>
                        <Select value={existingSurveyId} onChange={(e) => setExistingSurveyId(e.target.value)}>
                            {existingSurveys && existingSurveys.length > 0 ? (
                                existingSurveys.map((s) => (
                                    <MenuItem key={s.id} value={s.id}>{s.title}</MenuItem>
                                ))
                            ) : (
                                <MenuItem disabled>Нет доступных опросов</MenuItem>
                            )}
                        </Select>
                    </FormControl>
                )}

                {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}

                {preview && questions.length > 0 && (
                    <>
                        <Typography variant="h6" sx={{ mt: 3 }}>Предпросмотр первых 10 строк</Typography>
                        <TableContainer component={Paper} sx={{ mt: 1, maxHeight: 400 }}>
                            <Table size="small" stickyHeader>
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

                        <Typography variant="h6" sx={{ mt: 3 }}>Настройка вопросов (первые {visibleQuestions.length} из {questions.length})</Typography>
                        {questions.length > 20 && (
                            <Button
                                startIcon={showAllQuestions ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                onClick={() => setShowAllQuestions(!showAllQuestions)}
                                sx={{ mb: 2 }}
                            >
                                {showAllQuestions ? 'Свернуть' : 'Показать все вопросы'}
                            </Button>
                        )}
                        <Collapse in={true}>
                            {visibleQuestions.map((q, idx) => {
                                const originalIndex = questions.findIndex(qq => qq.originalName === q.originalName);
                                return (
                                    <Paper key={idx} sx={{ p: 2, mt: 2 }}>
                                        <TextField
                                            label="Текст вопроса"
                                            fullWidth
                                            value={q.text}
                                            onChange={(e) => handleQuestionChange(originalIndex, 'text', e.target.value)}
                                            sx={{ mb: 2 }}
                                        />
                                        <FormControl fullWidth sx={{ mb: 2 }}>
                                            <InputLabel>Тип вопроса</InputLabel>
                                            <Select value={q.type} onChange={(e) => handleQuestionChange(originalIndex, 'type', e.target.value)}>
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
                                                onChange={(e) => handleOptionsChange(originalIndex, e.target.value)}
                                                helperText="Например: Да, Нет, Возможно"
                                            />
                                        )}
                                        {q.type === 'scale' && (
                                            <Box sx={{ display: 'flex', gap: 2 }}>
                                                <TextField type="number" label="Min" value={q.scale_min} onChange={(e) => handleQuestionChange(originalIndex, 'scale_min', parseInt(e.target.value))} />
                                                <TextField type="number" label="Max" value={q.scale_max} onChange={(e) => handleQuestionChange(originalIndex, 'scale_max', parseInt(e.target.value))} />
                                            </Box>
                                        )}
                                    </Paper>
                                );
                            })}
                        </Collapse>
                        <Button variant="contained" onClick={handleCreateSurvey} disabled={loading} sx={{ mt: 3 }}>
                            {loading ? <CircularProgress size={24} /> : (importMode === 'new' ? 'Создать опрос и импортировать ответы' : 'Добавить ответы в опрос')}
                        </Button>
                    </>
                )}
            </Paper>
        </Box>
    );
}