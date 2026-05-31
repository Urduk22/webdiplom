import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TextField, Button, Paper, Typography, Box, Radio, RadioGroup, FormControlLabel, Checkbox, FormGroup, Alert, CircularProgress } from '@mui/material';
import { getSurveyByPublicId, submitResponse } from '../services/api';

export default function TakePublicSurvey() {
    const { publicId } = useParams();
    const navigate = useNavigate();
    const [survey, setSurvey] = useState(null);
    const [answers, setAnswers] = useState({});
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!publicId) {
            setError('Некорректная публичная ссылка');
            setLoading(false);
            return;
        }
        getSurveyByPublicId(publicId)
            .then(res => {
                setSurvey(res.data);
                setLoading(false);
            })
            .catch(() => {
                setError('Опрос не найден или ссылка недействительна');
                setLoading(false);
            });
    }, [publicId]);

    const handleAnswer = (questionId, value) => {
        setAnswers({ ...answers, [questionId]: value });
    };

    const handleMultiple = (questionId, optionId, checked) => {
        const current = answers[questionId] || [];
        if (checked) {
            setAnswers({ ...answers, [questionId]: [...current, optionId] });
        } else {
            setAnswers({ ...answers, [questionId]: current.filter(v => v !== optionId) });
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await submitResponse(survey.id, answers);
            setSuccess('Спасибо за участие!');
            setTimeout(() => navigate('/'), 3000);
        } catch (err) {
            setError('Ошибка отправки. Попробуйте позже.');
        }
    };

    if (loading) return <CircularProgress />;
    if (error) return <Alert severity="error">{error}</Alert>;
    if (!survey) return <Alert severity="warning">Опрос не найден</Alert>;

    return (
        <Box>
            <Typography variant="h4" gutterBottom>{survey.title}</Typography>
            <Typography variant="body1" paragraph>{survey.description}</Typography>
            <form onSubmit={handleSubmit}>
                {survey.questions.map((q, idx) => (
                    <Paper key={q.id} sx={{ p: 2, mb: 2 }}>
                        <Typography variant="h6">{idx+1}. {q.text}</Typography>
                        {q.question_type === 'text' && (
                            <TextField fullWidth multiline rows={2} onChange={(e) => handleAnswer(q.id, e.target.value)} />
                        )}
                        {q.question_type === 'scale' && (
                            <TextField type="number" inputProps={{ min: q.scale_min, max: q.scale_max }} onChange={(e) => handleAnswer(q.id, parseInt(e.target.value))} />
                        )}
                        {q.question_type === 'single' && (
                            <RadioGroup onChange={(e) => handleAnswer(q.id, parseInt(e.target.value))}>
                                {q.options.map(opt => <FormControlLabel key={opt.id} value={opt.id} control={<Radio />} label={opt.text} />)}
                            </RadioGroup>
                        )}
                        {q.question_type === 'multiple' && (
                            <FormGroup>
                                {q.options.map(opt => <FormControlLabel key={opt.id} control={<Checkbox onChange={(e) => handleMultiple(q.id, opt.id, e.target.checked)} />} label={opt.text} />)}
                            </FormGroup>
                        )}
                    </Paper>
                ))}
                {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}
                <Button variant="contained" type="submit">Отправить</Button>
            </form>
        </Box>
    );
}