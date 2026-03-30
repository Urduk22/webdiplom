import os
import shutil
import uuid
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import math
import traceback  # для детальной печати ошибок

# Импорты из core
from core.csv_utils import read_file_auto
from core.preprocessing import preprocess_data
from core.correlation import apply_correlation_threshold
from core.algorithm import do_n_launches_capped
from core.schemas import AnalysisParams, AnalysisResponse, FileUploadResponse

# Импорты для БД
from database import engine, Base, get_db
from models import Survey, Question, Option, Response, Answer

# Создание таблиц БД
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Survey Data Analyzer")

templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)


def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:
    file_ext = os.path.splitext(upload_file.filename)[1]
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path, upload_file.filename


def generate_correlation_graph(correlation_matrix, threshold=0.3):
    """Генерирует интерактивный граф корреляций с помощью Plotly (без networkx)."""
    columns = correlation_matrix.columns.tolist()
    n = len(columns)
    if n == 0:
        return "<p>Недостаточно данных для построения графа</p>"

    nodes = []
    edges = []
    for i, col in enumerate(columns):
        nodes.append({'id': i, 'label': col})
    for i in range(n):
        for j in range(i + 1, n):
            corr = correlation_matrix.iloc[i, j]
            if abs(corr) >= threshold:
                edges.append({
                    'from': i, 'to': j,
                    'value': abs(corr),
                    'color': '#FF4136' if corr < 0 else '#2ECC40'
                })

    if not edges:
        return "<p>Нет связей с корреляцией выше порога</p>"

    # Простая круговая расстановка узлов
    angle_step = 2 * math.pi / n
    pos = {}
    for i in range(n):
        angle = i * angle_step
        x = math.cos(angle)
        y = math.sin(angle)
        pos[i] = (x, y)

    edge_x, edge_y = [], []
    for edge in edges:
        x0, y0 = pos[edge['from']]
        x1, y1 = pos[edge['to']]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    )

    node_x = [pos[i][0] for i in range(n)]
    node_y = [pos[i][1] for i in range(n)]
    node_text = columns

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition='top center',
        hoverinfo='text',
        marker=dict(size=10, color='lightblue', line=dict(color='darkblue', width=1))
    )

    fig = go.Figure(data=[edge_trace, node_trace],
                    layout=go.Layout(
                        title='Граф корреляций между признаками',
                        showlegend=False,
                        hovermode='closest',
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                    ))
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')


def generate_results(df_processed, threshold, params, original_filename, process_details, correlation_details,
                     target_column=None):
    # Принудительно преобразуем все столбцы в числа (коэрциция NaN)
    for col in df_processed.columns:
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
    df_processed = df_processed.fillna(0)

    if target_column is not None:
        target_column = str(target_column).strip()

    correlation_matrix, _ = apply_correlation_threshold(df_processed, threshold)

    filtered = False
    if target_column and target_column in df_processed.columns:
        target_col = str(target_column)
        target_corr = correlation_matrix[target_col].drop(target_col, errors='ignore')
        relevant_columns = target_corr[abs(target_corr) > 0.3].index.tolist()
        if relevant_columns:
            df_filtered = df_processed[relevant_columns]
            correlation_matrix, _ = apply_correlation_threshold(df_filtered, threshold)
            filtered = True

    # Сохранение матрицы корреляции
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(original_filename)[0]
    corr_filename = f"{base_name}_correlation_{timestamp}.csv"
    corr_path = os.path.join(RESULTS_DIR, corr_filename)
    correlation_matrix.to_csv(corr_path)

    # Генерация графа
    graph_html = generate_correlation_graph(correlation_matrix, threshold=0.3)

    # Подготовка для алгоритма
    column_names = list(df_processed.columns if not filtered else df_filtered.columns)
    N = len(column_names)
    # Убедимся, что Adj_w – числовая матрица
    Adj_w = np.abs(correlation_matrix.values.astype(float))

    try:
        w_max, xD_best, plot_data = do_n_launches_capped(
            Adj_w,
            params['n_launches'],
            params['n_solutions'],
            params['frac'],
            params['q'],
            params['cap'],
            vocal=False
        )
    except Exception as e:
        print("Ошибка в алгоритме:")
        traceback.print_exc()
        raise

    selected_indices = xD_best.nonzero()[0]
    selected_columns = [column_names[i] for i in selected_indices if i < len(column_names)]

    algorithm_details = f"""ПАРАМЕТРЫ АЛГОРИТМА:
Количество запусков: {params['n_launches']}
Количество решений: {params['n_solutions']}
Параметр cap: {params['cap']}
Доля положительных: {params['frac']}
Параметр q: {params['q']}

Целевой признак: {target_column if target_column else 'не указан'}
Фильтрация по корреляции с целевым: {'применена' if filtered else 'не применялась'}

РЕЗУЛЬТАТЫ:
Максимальный вес: {w_max}
Количество выбранных столбцов: {len(selected_columns)}
Выбранные столбцы:"""

    for i, col in enumerate(selected_columns, 1):
        algorithm_details += f"\n{i}. {col}"

    if len(selected_columns) > 0:
        algorithm_details += f"\n\nИНДЕКСЫ ВЫБРАННЫХ СТОЛБЦОВ:"
        for i, col in enumerate(selected_columns, 1):
            col_index = column_names.index(col) if col in column_names else -1
            algorithm_details += f"\n{i}. {col} (индекс: {col_index})"

    algo_filename = f"{base_name}_algorithm_{timestamp}.txt"
    algo_path = os.path.join(RESULTS_DIR, algo_filename)
    with open(algo_path, "w", encoding="utf-8") as f:
        f.write(algorithm_details)

    return {
        "selected_columns": selected_columns,
        "w_max": w_max,
        "correlation_file": corr_filename,
        "algorithm_file": algo_filename,
        "num_rows": df_processed.shape[0],
        "num_cols": df_processed.shape[1],
        "process_details": process_details,
        "correlation_details": correlation_details,
        "algorithm_details": algorithm_details,
        "graph_html": graph_html
    }


# -------------------- ВЕБ-ИНТЕРФЕЙС --------------------
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze", response_class=HTMLResponse)
async def analyze_web(
        request: Request,
        file: UploadFile = File(...),
        drop_first: bool = Form(False),
        fill_na_zero: bool = Form(False),
        encode_cat: bool = Form(False),
        max_cat: int = Form(10),
        threshold: float = Form(0.3),
        n_launches: int = Form(10),
        n_solutions: int = Form(100),
        cap: int = Form(1000),
        frac: float = Form(0.35),
        q: float = Form(1.0),
        target_column: str = Form("")
):
    if not (0.0 <= threshold <= 1.0):
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Порог корреляции должен быть от 0.0 до 1.0"
        })

    try:
        file_path, original_filename = save_upload_file(file)
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Ошибка сохранения файла: {str(e)}"
        })

    try:
        df, delimiter, encoding = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        os.unlink(file_path)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Ошибка чтения файла: {str(e)}"
        })

    try:
        df_processed, process_details = preprocess_data(
            df,
            drop_first_column=drop_first,
            fill_na_with_zero=fill_na_zero,
            encode_categorical=encode_cat,
            max_categories=max_cat
        )
        if df_processed.empty:
            raise ValueError("После предобработки не осталось данных")
    except Exception as e:
        os.unlink(file_path)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Ошибка предобработки: {str(e)}"
        })

    target_column = str(target_column).strip() if target_column else ""
    if target_column and target_column not in df_processed.columns:
        warning = f"Столбец '{target_column}' не найден после предобработки. Фильтрация по целевому признаку не применялась."
        target_column = None
    else:
        warning = None

    _, correlation_details = apply_correlation_threshold(df_processed, threshold)

    params = {
        "n_launches": n_launches,
        "n_solutions": n_solutions,
        "cap": cap,
        "frac": frac,
        "q": q
    }

    try:
        results = generate_results(
            df_processed, threshold, params, original_filename,
            process_details, correlation_details,
            target_column=target_column if target_column else None
        )
    except Exception as e:
        os.unlink(file_path)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Ошибка анализа: {str(e)}"
        })

    os.unlink(file_path)

    return templates.TemplateResponse("result.html", {
        "request": request,
        "original_filename": original_filename,
        "selected_columns": results["selected_columns"],
        "w_max": results["w_max"],
        "correlation_file": results["correlation_file"],
        "algorithm_file": results["algorithm_file"],
        "num_rows": results["num_rows"],
        "num_cols": results["num_cols"],
        "threshold": threshold,
        "params": params,
        "drop_first": drop_first,
        "fill_na_zero": fill_na_zero,
        "encode_cat": encode_cat,
        "max_cat": max_cat,
        "target_column": target_column,
        "warning": warning,
        "process_details": results["process_details"],
        "correlation_details": results["correlation_details"],
        "algorithm_details": results["algorithm_details"],
        "graph_html": results["graph_html"]
    })


# -------------------- REST API --------------------
@app.post("/api/upload", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    file_path, original_filename = save_upload_file(file)
    file_id = os.path.basename(file_path).split('.')[0]
    return FileUploadResponse(file_id=file_id, filename=original_filename)


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_api(
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
        target_column: str = Form("")
):
    if not (0.0 <= threshold <= 1.0):
        raise HTTPException(status_code=400, detail="Порог корреляции должен быть от 0.0 до 1.0")

    try:
        file_path, original_filename = save_upload_file(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {str(e)}")

    try:
        df, delimiter, encoding = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")

    try:
        df_processed, process_details = preprocess_data(
            df,
            drop_first_column=drop_first,
            fill_na_with_zero=fill_na_zero,
            encode_categorical=encode_cat,
            max_categories=max_cat
        )
        if df_processed.empty:
            raise ValueError("После предобработки не осталось данных")
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(status_code=400, detail=f"Ошибка предобработки: {str(e)}")

    target_column = str(target_column).strip() if target_column else ""
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

    try:
        results = generate_results(
            df_processed, threshold, params, original_filename,
            process_details, correlation_details,
            target_column=target_column if target_column else None
        )
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")

    os.unlink(file_path)

    results["target_column"] = target_column if target_column else ""
    return AnalysisResponse(**results)


@app.get("/api/download/{filename}")
async def download_file_api(filename: str):
    file_path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/octet-stream', filename=filename)
    raise HTTPException(status_code=404, detail="File not found")


# -------------------- ОПРОСЫ --------------------
@app.get("/surveys", response_class=HTMLResponse)
async def list_surveys(request: Request, db: Session = Depends(get_db)):
    surveys = db.query(Survey).order_by(Survey.created_at.desc()).all()
    return templates.TemplateResponse("surveys_list.html", {"request": request, "surveys": surveys})


@app.get("/surveys/new", response_class=HTMLResponse)
async def create_survey_form(request: Request):
    return templates.TemplateResponse("create_survey.html", {"request": request})


@app.post("/api/surveys", response_class=RedirectResponse)
async def create_survey_api(survey_data: dict, db: Session = Depends(get_db)):
    title = survey_data.get("title")
    description = survey_data.get("description", "")
    questions_data = survey_data.get("questions", [])

    db_survey = Survey(title=title, description=description)
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)

    for q in questions_data:
        db_q = Question(
            survey_id=db_survey.id,
            text=q["text"],
            question_type=q["question_type"],
            order=q["order"]
        )
        db.add(db_q)
        db.commit()
        db.refresh(db_q)

        if q["question_type"] in ["single", "multiple"]:
            for opt_text in q.get("options", []):
                db_opt = Option(question_id=db_q.id, text=opt_text)
                db.add(db_opt)
        db.commit()

    return RedirectResponse(url=f"/surveys/{db_survey.id}", status_code=303)


@app.get("/surveys/{survey_id}", response_class=HTMLResponse)
async def take_survey(request: Request, survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        return HTMLResponse("Опрос не найден", status_code=404)
    return templates.TemplateResponse("take_survey.html", {"request": request, "survey": survey})


@app.post("/surveys/{survey_id}/submit")
async def submit_survey(survey_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    response = Response(survey_id=survey_id)
    db.add(response)
    db.commit()
    db.refresh(response)

    for key, value in form.items():
        if key.startswith("q_"):
            try:
                q_id = int(key[2:])
            except:
                continue
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
                if value:
                    try:
                        answer.option_id = int(value)
                    except:
                        pass
            elif question.question_type == 'multiple':
                answer.multiple_option_ids = value
            db.add(answer)
    db.commit()
    return {"message": "Спасибо за участие!"}


@app.get("/surveys/{survey_id}/results", response_class=HTMLResponse)
async def survey_results(request: Request, survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        return HTMLResponse("Опрос не найден", status_code=404)
    responses_count = db.query(Response).filter(Response.survey_id == survey_id).count()
    return templates.TemplateResponse("survey_results.html", {
        "request": request,
        "survey": survey,
        "responses_count": responses_count
    })


@app.post("/surveys/{survey_id}/analyze")
async def analyze_survey(
        survey_id: int,
        request: Request,
        db: Session = Depends(get_db),
        threshold: float = Form(0.3),
        n_launches: int = Form(10),
        n_solutions: int = Form(100),
        cap: int = Form(1000),
        frac: float = Form(0.35),
        q: float = Form(1.0),
        drop_first: bool = Form(False),
        fill_na_zero: bool = Form(True),
        encode_cat: bool = Form(True),
        max_cat: int = Form(10),
        target_column: str = Form("")
):
    # Приводим target_column к строке и очищаем
    target_column = str(target_column).strip() if target_column else ""

    # Получаем все ответы
    responses = db.query(Response).filter(Response.survey_id == survey_id).all()
    if not responses:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {
            "request": request,
            "survey": survey,
            "responses_count": 0,
            "error": "Нет данных для анализа"
        })

    # Получаем вопросы, сортируем по order
    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()

    # Строим DataFrame из ответов
    data = {}
    for q in questions:
        col_name = f"q{q.id}"  # имя столбца = q<id>
        values = []
        for r in responses:
            # Получаем ответ на данный вопрос
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

    # Создаём DataFrame
    df = pd.DataFrame(data)

    # Проверка: если в DataFrame нет строк или столбцов
    if df.empty:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {
            "request": request,
            "survey": survey,
            "responses_count": len(responses),
            "error": "Не удалось сформировать DataFrame из ответов"
        })

    # Предобработка
    try:
        df_processed, process_details = preprocess_data(
            df,
            drop_first_column=drop_first,
            fill_na_with_zero=fill_na_zero,
            encode_categorical=encode_cat,
            max_categories=max_cat
        )
    except Exception as e:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {
            "request": request,
            "survey": survey,
            "responses_count": len(responses),
            "error": f"Ошибка предобработки: {str(e)}"
        })

    if df_processed.empty:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {
            "request": request,
            "survey": survey,
            "responses_count": len(responses),
            "error": "После предобработки не осталось данных"
        })

    # Проверка целевого столбца (теперь df_processed.columns — это строки)
    if target_column and target_column not in df_processed.columns:
        target_column = None

    # Корреляция
    try:
        _, correlation_details = apply_correlation_threshold(df_processed, threshold)
    except Exception as e:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {
            "request": request,
            "survey": survey,
            "responses_count": len(responses),
            "error": f"Ошибка вычисления корреляции: {str(e)}"
        })

    params = {
        "n_launches": n_launches,
        "n_solutions": n_solutions,
        "cap": cap,
        "frac": frac,
        "q": q
    }

    # Запуск анализа
    try:
        results = generate_results(
            df_processed, threshold, params, f"survey_{survey_id}",
            process_details, correlation_details,
            target_column=target_column if target_column else None
        )
    except Exception as e:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {
            "request": request,
            "survey": survey,
            "responses_count": len(responses),
            "error": f"Ошибка анализа: {str(e)}"
        })

    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    return templates.TemplateResponse("survey_results.html", {
        "request": request,
        "survey": survey,
        "responses_count": len(responses),
        "results": results,
        "target_column": target_column
    })
@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Скачивание файла результатов (корреляция или алгоритм).
    """
    file_path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/octet-stream', filename=filename)
    raise HTTPException(status_code=404, detail="File not found")