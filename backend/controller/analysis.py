from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from backend.service.auth_service import get_current_user
from backend.service.analysis_service import save_upload_file, generate_results
from core.csv_utils import read_file_auto
from core.preprocessing import preprocess_data
from core.correlation import apply_correlation_threshold

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
    target_column: str = Form(""),     # номер столбца (начиная с 1)
    method: str = Form("graph"),
    top_k: int = Form(10),
    current_user = Depends(get_current_user)
):
    # Сохраняем загруженный файл
    file_path, original_filename = save_upload_file(file)
    try:
        df, _, _ = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        import os
        os.unlink(file_path)
        raise HTTPException(400, f"Ошибка чтения файла: {str(e)}")

    # Предобработка
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

    # Преобразование номера целевого столбца в имя
    target_col_name = None
    if target_column and target_column.strip():
        try:
            col_idx = int(target_column) - 1
            if 0 <= col_idx < len(df_processed.columns):
                target_col_name = df_processed.columns[col_idx]
        except ValueError:
            pass

    # Корреляционная матрица
    _, correlation_details = apply_correlation_threshold(df_processed, threshold)

    # Параметры алгоритма
    params = {
        "n_launches": n_launches,
        "n_solutions": n_solutions,
        "cap": cap,
        "frac": frac,
        "q": q
    }

    # Запуск анализа
    results = generate_results(
        df_processed, threshold, params, original_filename,
        process_details, correlation_details,
        target_column=target_col_name,
        method=method,
        top_k=top_k
    )

    # Удаляем временный файл
    import os
    os.unlink(file_path)

    return results


@router.post("/surveys/{survey_id}/analyze")
async def analyze_survey(
    survey_id: int,
    params: dict,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Динамические импорты для избежания циклических зависимостей
    from backend.service.analysis_service import generate_results
    from models import Survey, Question, Option, Response, Answer
    from core.preprocessing import preprocess_data
    from core.correlation import apply_correlation_threshold
    import pandas as pd

    # Проверка существования опроса и прав доступа
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Опрос не найден")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Доступ запрещён")

    # Получение ответов
    responses = db.query(Response).filter(Response.survey_id == survey_id).all()
    if not responses:
        raise HTTPException(400, "Нет ответов для анализа")

    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()

    # Формирование DataFrame
    data = {}
    for q in questions:
        col_name = f"q{q.id}"
        values = []
        for r in responses:
            answer = db.query(Answer).filter(Answer.response_id == r.id, Answer.question_id == q.id).first()
            if answer:
                if q.question_type == 'text':
                    val = answer.text_value
                elif q.question_type == 'scale':
                    val = answer.numeric_value
                elif q.question_type == 'single':
                    if answer.option_id:
                        opt = db.query(Option).filter(Option.id == answer.option_id).first()
                        val = opt.text if opt else None
                    else:
                        val = None
                elif q.question_type == 'multiple':
                    val = answer.multiple_option_ids
                else:
                    val = None
            else:
                val = None
            values.append(val)
        data[col_name] = values

    df = pd.DataFrame(data)

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

    # Преобразование номера целевого столбца в имя
    target_col_name = None
    target_col_str = params.get('target_column', '')
    if target_col_str and str(target_col_str).strip():
        try:
            col_idx = int(target_col_str) - 1
            if 0 <= col_idx < len(df_processed.columns):
                target_col_name = df_processed.columns[col_idx]
        except ValueError:
            pass

    # Корреляционная матрица
    _, correlation_details = apply_correlation_threshold(df_processed, params.get('threshold', 0.3))

    # Параметры алгоритма
    algo_params = {
        'n_launches': params.get('n_launches', 10),
        'n_solutions': params.get('n_solutions', 100),
        'cap': params.get('cap', 1000),
        'frac': params.get('frac', 0.35),
        'q': params.get('q', 1.0)
    }
    method = params.get('method', 'graph')
    top_k = params.get('top_k', 10)

    # Запуск анализа
    results = generate_results(
        df_processed, params.get('threshold', 0.3), algo_params,
        f"survey_{survey_id}", process_details, correlation_details,
        target_column=target_col_name,
        method=method,
        top_k=top_k
    )
    return results