import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  TextField, Button, Paper, Typography, Box, IconButton, MenuItem, Select, FormControl, InputLabel,
  Grid, Card, CardContent
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import AddIcon from '@mui/icons-material/Add';
import { createSurvey } from '../services/api';

export default function CreateSurvey() {
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [questions, setQuestions] = useState([]);

  const addQuestion = () => {
    setQuestions([...questions, {
      text: '',
      question_type: 'text',
      options: [],
      scale_min: 1,
      scale_max: 10
    }]);
  };

  const removeQuestion = (index) => {
    const newQuestions = [...questions];
    newQuestions.splice(index, 1);
    setQuestions(newQuestions);
  };

  const updateQuestion = (index, field, value) => {
    const newQuestions = [...questions];
    newQuestions[index][field] = value;
    setQuestions(newQuestions);
  };

  const updateOptions = (index, value) => {
    const options = value.split('\n').filter(o => o.trim() !== '');
    updateQuestion(index, 'options', options);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      title,
      description,
      questions: questions.map((q, idx) => ({
        text: q.text,
        question_type: q.question_type,
        order: idx,
        options: q.options,
        scale_min: q.scale_min,
        scale_max: q.scale_max
      }))
    };
    try {
      await createSurvey(payload);
      navigate('/surveys');
    } catch (err) {
    const data = err.response?.data;
    let errorMsg = 'Ошибка создания опроса';
    if (data) {
        if (typeof data === 'string') errorMsg = data;
        else if (data.detail) errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        else if (data.message) errorMsg = data.message;
        else errorMsg = JSON.stringify(data);
    }
    alert(errorMsg);
    }
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>Создание опроса</Typography>
      <Paper sx={{ p: 3 }}>
        <form onSubmit={handleSubmit}>
          <TextField fullWidth label="Название опроса" margin="normal" value={title} onChange={(e) => setTitle(e.target.value)} required />
          <TextField fullWidth label="Описание" margin="normal" multiline rows={2} value={description} onChange={(e) => setDescription(e.target.value)} />

          <Typography variant="h6" sx={{ mt: 2 }}>Вопросы</Typography>
          {questions.map((q, idx) => (
            <Card key={idx} sx={{ mt: 2 }}>
              <CardContent>
                <Grid container spacing={2}>
                  <Grid item xs={12}>
                    <TextField fullWidth label="Текст вопроса" value={q.text} onChange={(e) => updateQuestion(idx, 'text', e.target.value)} required />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <FormControl fullWidth>
                      <InputLabel>Тип вопроса</InputLabel>
                      <Select value={q.question_type} onChange={(e) => updateQuestion(idx, 'question_type', e.target.value)}>
                        <MenuItem value="text">Текстовый ответ</MenuItem>
                        <MenuItem value="single">Одиночный выбор</MenuItem>
                        <MenuItem value="multiple">Множественный выбор</MenuItem>
                        <MenuItem value="scale">Числовая шкала</MenuItem>
                      </Select>
                    </FormControl>
                  </Grid>
                  {(q.question_type === 'single' || q.question_type === 'multiple') && (
                    <Grid item xs={12}>
                      <TextField fullWidth label="Варианты ответа (каждый с новой строки)" multiline rows={3} onChange={(e) => updateOptions(idx, e.target.value)} />
                    </Grid>
                  )}
                  {q.question_type === 'scale' && (
                    <>
                      <Grid item xs={6}>
                        <TextField fullWidth type="number" label="Мин. значение" value={q.scale_min} onChange={(e) => updateQuestion(idx, 'scale_min', parseInt(e.target.value))} />
                      </Grid>
                      <Grid item xs={6}>
                        <TextField fullWidth type="number" label="Макс. значение" value={q.scale_max} onChange={(e) => updateQuestion(idx, 'scale_max', parseInt(e.target.value))} />
                      </Grid>
                    </>
                  )}
                </Grid>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                  <IconButton onClick={() => removeQuestion(idx)} color="error"><DeleteIcon /></IconButton>
                </Box>
              </CardContent>
            </Card>
          ))}
          <Button startIcon={<AddIcon />} onClick={addQuestion} sx={{ mt: 2 }}>Добавить вопрос</Button>
          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 3 }}>
            <Button variant="contained" type="submit">Создать опрос</Button>
          </Box>
        </form>
      </Paper>
    </Box>
  );
}