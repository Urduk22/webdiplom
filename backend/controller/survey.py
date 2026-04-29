from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Survey, Question, Option, Response, Answer
from backend.service.auth_service import get_current_user
from backend.service.survey_service import get_survey_stats_data
from core.schemas import SurveyCreate
import io
import pandas as pd

router = APIRouter(prefix="/api", tags=["surveys"])

@router.get("/surveys")
async def list_surveys(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user.role == "admin":
        surveys = db.query(Survey).all()
    else:
        surveys = db.query(Survey).filter(Survey.owner_id == current_user.id).all()
    return surveys

@router.get("/surveys/{survey_id}")
async def get_survey(survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()
    result = {
        "id": survey.id,
        "title": survey.title,
        "description": survey.description,
        "created_at": survey.created_at,
        "questions": []
    }
    for q in questions:
        options = db.query(Option).filter(Option.question_id == q.id).all()
        result["questions"].append({
            "id": q.id,
            "text": q.text,
            "question_type": q.question_type,
            "scale_min": q.scale_min,
            "scale_max": q.scale_max,
            "options": [{"id": opt.id, "text": opt.text} for opt in options]
        })
    return result

@router.post("/surveys")
async def create_survey(survey_data: SurveyCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    db_survey = Survey(title=survey_data.title, description=survey_data.description, owner_id=current_user.id)
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)
    for idx, q in enumerate(survey_data.questions):
        db_q = Question(
            survey_id=db_survey.id,
            text=q.text,
            question_type=q.question_type,
            order=q.order,
            scale_min=q.scale_min,
            scale_max=q.scale_max
        )
        db.add(db_q)
        db.commit()
        db.refresh(db_q)
        if q.question_type in ["single", "multiple"]:
            for opt_text in q.options:
                db_opt = Option(question_id=db_q.id, text=opt_text)
                db.add(db_opt)
        db.commit()
    return {"id": db_survey.id, "message": "Survey created"}

@router.delete("/surveys/{survey_id}")
async def delete_survey(survey_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not allowed")
    db.delete(survey)
    db.commit()
    return {"message": "Deleted"}

@router.post("/surveys/{survey_id}/submit")
async def submit_response(survey_id: int, answers: dict, db: Session = Depends(get_db)):
    response = Response(survey_id=survey_id)
    db.add(response)
    db.commit()
    db.refresh(response)
    for q_id_str, value in answers.items():
        q_id = int(q_id_str)
        question = db.query(Question).filter(Question.id == q_id).first()
        if not question:
            continue
        answer = Answer(response_id=response.id, question_id=q_id)
        if question.question_type == 'text':
            answer.text_value = value
        elif question.question_type == 'scale':
            try:
                answer.numeric_value = float(value)
            except:
                pass
        elif question.question_type == 'single':
            try:
                answer.option_id = int(value)
            except:
                pass
        elif question.question_type == 'multiple':
            if isinstance(value, list):
                answer.multiple_option_ids = ','.join(str(v) for v in value)
            else:
                answer.multiple_option_ids = str(value)
        db.add(answer)
    db.commit()
    return {"message": "Thank you!"}

@router.get("/surveys/{survey_id}/stats")
async def get_survey_stats(survey_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not allowed")
    stats = get_survey_stats_data(survey_id, db)
    return stats

@router.get("/surveys/{survey_id}/export-stats")
async def export_survey_stats_excel(survey_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not allowed")
    stats = get_survey_stats_data(survey_id, db)
    if not stats:
        raise HTTPException(404, "No data")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for q_stat in stats:
            if q_stat['type'] == 'single':
                df = pd.DataFrame(q_stat['data'])
                df.columns = ['Вариант', 'Голосов', 'Процент']
            elif q_stat['type'] == 'multiple':
                df = pd.DataFrame(q_stat['data'])
                df.columns = ['Вариант', 'Выборов', 'Процент от опрошенных']
            elif q_stat['type'] == 'scale':
                df = pd.DataFrame(q_stat['data'])
                df.columns = ['Оценка', 'Количество']
                mean_row = pd.DataFrame([['Среднее', q_stat['mean']]], columns=['Оценка', 'Количество'])
                median_row = pd.DataFrame([['Медиана', q_stat['median']]], columns=['Оценка', 'Количество'])
                df = pd.concat([df, mean_row, median_row], ignore_index=True)
            else:
                df = pd.DataFrame(q_stat.get('answers', []), columns=['Текстовые ответы'])
            sheet_name = q_stat['text'][:31]
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=survey_{survey_id}_stats.xlsx"}
    )