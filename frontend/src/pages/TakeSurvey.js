import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { TextField, Button, Paper, Typography, Box, Radio, RadioGroup, FormControlLabel, Checkbox, FormGroup, Alert } from '@mui/material';
import { getSurvey, submitResponse } from '../services/api';

export default function TakeSurvey() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [survey, setSurvey] = useState(null);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    getSurvey(id).then(res => setSurvey(res.data)).catch(() => setError('Опрос не найден'));
  }, [id]);

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
      await submitResponse(id, answers);
      setSuccess('Спасибо за участие!');
      setTimeout(() => navigate('/'), 2000);
    } catch (err) {
    const data = err.response?.data;
    let errorMsg = 'Ошибка отправки';
    if (data) {
        if (typeof data === 'string') errorMsg = data;
        else if (data.detail) errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        else if (data.message) errorMsg = data.message;
        else errorMsg = JSON.stringify(data);
    }
    setError(errorMsg);
    }
  };

  if (error) return <Alert severity="error">{error}</Alert>;
  if (!survey) return <div>Загрузка...</div>;

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