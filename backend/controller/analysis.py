from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from database import get_db
from backend.service.auth_service import get_current_user
from backend.service.analysis_service import save_upload_file, generate_results, generate_pdf_report_from_df
from core.csv_utils import read_file_auto
from core.preprocessing import preprocess_data
from core.correlation import apply_correlation_threshold
import pandas as pd
import numpy as np
from models import Survey, Question, Option, Response, Answer

router = APIRouter(prefix="/api", tags=["analysis"])

@router.post("/analyze")
async def analyze_file(
    file: UploadFile = File(...),
    drop_first: bool = Form(False),
    fill_na_zero: bool = Form(True),
    encode_cat: bool = Form(False),
    max_cat: int = Form(10),
    threshold: float = Form(0.3),
    n_launches: int = Form(10),
    n_solutions: int = Form(100),
    cap: int = Form(1000),
    frac: float = Form(0.35),
    q: float = Form(1.0),
    target_column: str = Form(""),
    method: str = Form("graph"),
    top_k: int = Form(10),
):
    file_path, original_filename = save_upload_file(file)
    try:
        df, _, _ = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        import os
        os.unlink(file_path)
        raise HTTPException(400, f"Ошибка чтения файла: {str(e)}")
    df_processed, process_details = preprocess_data(
        df,
        drop_first_column=drop_first,
        fill_na_with_zero=fill_na_zero,
        encode_categorical=encode_cat,
        max_categories=max_cat
    )
    if df_processed.empty:
        import os
        os.unlink(file_path)
        raise HTTPException(400, "После предобработки не осталось данных")
    if target_column and target_column not in df_processed.columns:
        target_column = None
    _, correlation_details = apply_correlation_threshold(df_processed, threshold)
    params = {
        "n_launches": n_launches,
        "n_solutions": n_solutions,
        "cap": cap,
        "frac": frac,
        "q": q
    }
    results = generate_results(
        df_processed, threshold, params, original_filename,
        process_details, correlation_details,
        target_column=target_column if target_column else None,
        method=method,
        top_k=top_k
    )
    import os
    os.unlink(file_path)
    return results

@router.post("/analyze/export-pdf")
async def export_analysis_pdf(
    file: UploadFile = File(...),
    drop_first: bool = Form(False),
    fill_na_zero: bool = Form(True),
    encode_cat: bool = Form(False),
    max_cat: int = Form(10),
    threshold: float = Form(0.3),
    n_launches: int = Form(10),
    n_solutions: int = Form(100),
    cap: int = Form(1000),
    frac: float = Form(0.35),
    q: float = Form(1.0),
    target_column: str = Form(""),
    method: str = Form("graph"),
    top_k: int = Form(10),
):
    # Выполняем анализ (как в /analyze) и генерируем PDF
    file_path, original_filename = save_upload_file(file)
    try:
        df, _, _ = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        import os
        os.unlink(file_path)
        raise HTTPException(400, f"Ошибка чтения файла: {str(e)}")
    df_processed, process_details = preprocess_data(
        df,
        drop_first_column=drop_first,
        fill_na_with_zero=fill_na_zero,
        encode_categorical=encode_cat,
        max_categories=max_cat
    )
    if df_processed.empty:
        import os
        os.unlink(file_path)
        raise HTTPException(400, "После предобработки не осталось данных")
    if target_column and target_column not in df_processed.columns:
        target_column = None
    _, correlation_details = apply_correlation_threshold(df_processed, threshold)
    params = {
        "n_launches": n_launches,
        "n_solutions": n_solutions,
        "cap": cap,
        "frac": frac,
        "q": q
    }
    results = generate_results(
        df_processed, threshold, params, original_filename,
        process_details, correlation_details,
        target_column=target_column if target_column else None,
        method=method,
        top_k=top_k
    )
    import os
    os.unlink(file_path)

    pdf_buffer = generate_pdf_report_from_df(results, df_processed)
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=analysis_report.pdf"}
    )

@router.post("/surveys/{survey_id}/analyze")
async def analyze_survey(
    survey_id: int,
    params: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Оптимизированный сбор данных из БД
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Опрос не найден")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Доступ запрещён")

    # Получаем все ответы одним запросом с JOIN
    rows = db.query(
        Response.id.label('response_id'),
        Question.id.label('question_id'),
        Question.question_type,
        Answer.text_value,
        Answer.numeric_value,
        Answer.option_id,
        Answer.multiple_option_ids,
        Option.text.label('option_text')
    ).join(Answer, Answer.response_id == Response.id)\
     .join(Question, Question.id == Answer.question_id)\
     .outerjoin(Option, Option.id == Answer.option_id)\
     .filter(Response.survey_id == survey_id).all()

    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()
    question_by_id = {q.id: q for q in questions}

    # Группируем по response_id
    data_by_response = {}
    for row in rows:
        rid = row.response_id
        qid = row.question_id
        if rid not in data_by_response:
            data_by_response[rid] = {}
        q = question_by_id.get(qid)
        if not q:
            continue
        col_name = f"q{qid}"
        if q.question_type == 'text':
            val = row.text_value
        elif q.question_type == 'scale':
            val = row.numeric_value
        elif q.question_type == 'single':
            val = row.option_text if row.option_id else None
        elif q.question_type == 'multiple':
            val = row.multiple_option_ids
        else:
            val = None
        data_by_response[rid][col_name] = val

    # DataFrame
    df = pd.DataFrame.from_dict(data_by_response, orient='index')
    for q in questions:
        col = f"q{q.id}"
        if col not in df.columns:
            df[col] = None

    # Предобработка
    df_processed, process_details = preprocess_data(
        df,
        drop_first_column=params.get('drop_first', False),
        fill_na_with_zero=params.get('fill_na_zero', True),
        encode_categorical=params.get('encode_cat', True),
        max_categories=params.get('max_cat', 10)
    )
    if df_processed.empty:
        raise HTTPException(400, "После предобработки не осталось данных")

    target_col_name = None
    target_col_str = params.get('target_column', '')
    if target_col_str and str(target_col_str).strip():
        try:
            col_idx = int(target_col_str) - 1
            if 0 <= col_idx < len(df_processed.columns):
                target_col_name = df_processed.columns[col_idx]
        except ValueError:
            pass

    _, correlation_details = apply_correlation_threshold(df_processed, params.get('threshold', 0.3))

    algo_params = {
        'n_launches': params.get('n_launches', 10),
        'n_solutions': params.get('n_solutions', 100),
        'cap': params.get('cap', 1000),
        'frac': params.get('frac', 0.35),
        'q': params.get('q', 1.0)
    }
    method = params.get('method', 'graph')
    top_k = params.get('top_k', 10)

    from backend.service.analysis_service import generate_results
    results = generate_results(
        df_processed, params.get('threshold', 0.3), algo_params,
        f"survey_{survey_id}", process_details, correlation_details,
        target_column=target_col_name,
        method=method,
        top_k=top_k
    )
    return results