from sqlalchemy.orm import Session
from models import Survey, Question, Option, Response, Answer
import numpy as np

def get_survey_stats_data(survey_id: int, db: Session):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        return None
    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()
    responses = db.query(Response).filter(Response.survey_id == survey_id).all()
    total_responses = len(responses)

    stats = []
    for q in questions:
        answers = db.query(Answer).filter(Answer.question_id == q.id).all()
        if q.question_type == 'single':
            options = db.query(Option).filter(Option.question_id == q.id).all()
            opt_counts = {opt.id: 0 for opt in options}
            for a in answers:
                if a.option_id and a.option_id in opt_counts:
                    opt_counts[a.option_id] += 1
            data = [{
                "text": opt.text,
                "count": opt_counts[opt.id],
                "percent": round(opt_counts[opt.id] / total_responses * 100, 2) if total_responses else 0
            } for opt in options]
            stats.append({
                "id": q.id,
                "text": q.text,
                "type": "single",
                "data": data,
                "total": total_responses
            })
        elif q.question_type == 'multiple':
            options = db.query(Option).filter(Option.question_id == q.id).all()
            option_by_id = {opt.id: opt.text for opt in options}
            option_counts = {opt.text: 0 for opt in options}
            for a in answers:
                if a.multiple_option_ids:
                    ids = [int(x) for x in a.multiple_option_ids.split(',') if x.strip().isdigit()]
                    for opt_id in ids:
                        if opt_id in option_by_id:
                            opt_text = option_by_id[opt_id]
                            option_counts[opt_text] += 1
            data = [{
                "text": text,
                "count": count,
                "percent": round(count / total_responses * 100, 2) if total_responses else 0
            } for text, count in option_counts.items()]
            stats.append({
                "id": q.id,
                "text": q.text,
                "type": "multiple",
                "data": data,
                "total": total_responses
            })
        elif q.question_type == 'scale':
            values = [a.numeric_value for a in answers if a.numeric_value is not None]
            if values:
                hist = {}
                for v in range(q.scale_min, q.scale_max + 1):
                    hist[v] = values.count(v)
                data = [{"value": v, "count": c} for v, c in hist.items()]
                mean = round(sum(values) / len(values), 2)
                median = round(np.median(values), 2)
            else:
                data = []
                mean = median = 0
            stats.append({
                "id": q.id,
                "text": q.text,
                "type": "scale",
                "data": data,
                "mean": mean,
                "median": median,
                "min": q.scale_min,
                "max": q.scale_max,
                "total": len(values)
            })
        else:
            text_answers = [a.text_value for a in answers if a.text_value]
            stats.append({
                "id": q.id,
                "text": q.text,
                "type": "text",
                "answers": text_answers[:50],
                "total": len(text_answers)
            })
    return stats