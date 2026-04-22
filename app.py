import os
import shutil
import uuid
import io
import tempfile
import pickle
import json
from datetime import datetime, timedelta
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import math
import traceback
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from passlib.context import CryptContext
import jwt
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_classif, f_regression

# Импорты из core
from core.csv_utils import read_file_auto
from core.preprocessing import preprocess_data
from core.correlation import apply_correlation_threshold
from core.algorithm import do_n_launches_capped

# Импорты для БД
from database import engine, Base, get_db
from models import User, Survey, Question, Option, Response, Answer

# Создание таблиц БД
Base.metadata.create_all(bind=engine)

# --- Настройка приложения ---
app = FastAPI(title="Survey Data Analyzer API")

# CORS для React фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Папки для загрузки и результатов ---
UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- Конфигурация аутентификации ---
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token")
def convert_numpy_types(obj):
    """Рекурсивно преобразует numpy типы в стандартные Python типы."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    return obj
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(db: Session, username: str, password: str):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# --- Вспомогательные функции для графиков и отчётов ---
def generate_correlation_graph(correlation_matrix, threshold=0.3):
    columns = correlation_matrix.columns.tolist()
    n = len(columns)
    if n == 0:
        return "<p>Недостаточно данных для построения графа</p>"
    nodes = []
    edges = []
    for i, col in enumerate(columns):
        nodes.append({'id': i, 'label': col})
    for i in range(n):
        for j in range(i+1, n):
            corr = correlation_matrix.iloc[i, j]
            if abs(corr) >= threshold:
                edges.append({'from': i, 'to': j, 'value': abs(corr), 'color': '#FF4136' if corr < 0 else '#2ECC40'})
    if not edges:
        return "<p>Нет связей с корреляцией выше порога</p>"
    angle_step = 2 * math.pi / n
    pos = {i: (math.cos(i*angle_step), math.sin(i*angle_step)) for i in range(n)}
    edge_x, edge_y = [], []
    for edge in edges:
        x0, y0 = pos[edge['from']]
        x1, y1 = pos[edge['to']]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
    edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.5, color='#888'), hoverinfo='none', mode='lines')
    node_trace = go.Scatter(
        x=[pos[i][0] for i in range(n)], y=[pos[i][1] for i in range(n)],
        mode='markers+text', text=columns, textposition='top center', hoverinfo='text',
        marker=dict(size=10, color='lightblue', line=dict(color='darkblue', width=1))
    )
    fig = go.Figure(data=[edge_trace, node_trace], layout=go.Layout(
        title='Граф корреляций', showlegend=False, hovermode='closest',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    ))
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_correlation_heatmap(correlation_matrix):
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix.values, x=correlation_matrix.columns, y=correlation_matrix.columns,
        colorscale='RdBu', zmid=0, text=correlation_matrix.values.round(2), texttemplate='%{text}',
        textfont={"size": 8}, hoverongaps=False
    ))
    fig.update_layout(title='Матрица корреляций', xaxis_title='Признаки', yaxis_title='Признаки', width=800, height=800)
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_pca_plot(df_processed, n_components=5):
    n = min(n_components, df_processed.shape[1])
    pca = PCA(n_components=n)
    pca.fit(df_processed)
    explained_variance = pca.explained_variance_ratio_
    cumulative = np.cumsum(explained_variance)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[f'PC{i+1}' for i in range(n)], y=explained_variance, name='Объяснённая дисперсия', marker_color='lightblue'))
    fig.add_trace(go.Scatter(x=[f'PC{i+1}' for i in range(n)], y=cumulative, name='Кумулятивная дисперсия', mode='lines+markers', marker_color='darkblue', yaxis='y2'))
    fig.update_layout(title='PCA: объяснённая дисперсия', xaxis_title='Главные компоненты', yaxis_title='Доля дисперсии',
                      yaxis2=dict(title='Кумулятивная доля', overlaying='y', side='right'), hovermode='closest')
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:
    file_ext = os.path.splitext(upload_file.filename)[1]
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path, upload_file.filename

def generate_results(df_processed, threshold, params, original_filename, process_details, correlation_details, target_column=None, method="graph", top_k=10):
    # Принудительное преобразование в числа
    for col in df_processed.columns:
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
    df_processed = df_processed.fillna(0)

    if target_column is not None:
        target_column = str(target_column).strip()
    correlation_matrix, _ = apply_correlation_threshold(df_processed, threshold)

    filtered = False
    if target_column and target_column in df_processed.columns:
        target_corr = correlation_matrix[target_column].drop(target_column, errors='ignore')
        relevant_columns = target_corr[abs(target_corr) > 0.3].index.tolist()
        if relevant_columns:
            df_filtered = df_processed[relevant_columns]
            correlation_matrix, _ = apply_correlation_threshold(df_filtered, threshold)
            filtered = True

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(original_filename)[0]
    corr_filename = f"{base_name}_correlation_{timestamp}.csv"
    corr_path = os.path.join(RESULTS_DIR, corr_filename)
    correlation_matrix.to_csv(corr_path)

    heatmap_html = generate_correlation_heatmap(correlation_matrix)
    graph_html = generate_correlation_graph(correlation_matrix, threshold=0.3)
    pca_html = ""
    if method == 'pca':
        pca_html = generate_pca_plot(df_processed, min(top_k, df_processed.shape[1]))

    selected_columns = []
    w_max = 0
    algorithm_details = ""
    if method == "graph":
        column_names = list(df_processed.columns if not filtered else df_filtered.columns)
        N = len(column_names)
        Adj_w = np.abs(correlation_matrix.values.astype(float))
        try:
            w_max, xD_best, _ = do_n_launches_capped(
                Adj_w, params['n_launches'], params['n_solutions'],
                params['frac'], params['q'], params['cap'], vocal=False
            )
            selected_columns = [column_names[i] for i in xD_best.nonzero()[0] if i < len(column_names)]
        except Exception as e:
            traceback.print_exc()
            raise
        algorithm_details = f"""ПАРАМЕТРЫ АЛГОРИТМА:
Количество запусков: {params['n_launches']}
Количество решений: {params['n_solutions']}
Cap: {params['cap']}, Frac: {params['frac']}, q: {params['q']}
Целевой признак: {target_column if target_column else 'не указан'}
Фильтрация: {'применена' if filtered else 'не применялась'}
РЕЗУЛЬТАТЫ:
Максимальный вес: {w_max}
Выбрано столбцов: {len(selected_columns)}
Выбранные столбцы:""" + "\n".join([f"{i+1}. {col}" for i, col in enumerate(selected_columns)])
    else:
        algorithm_details = f"Выбран метод: {method}. Результаты сравнения будут показаны отдельно."

    algo_filename = f"{base_name}_algorithm_{timestamp}.txt"
    algo_path = os.path.join(RESULTS_DIR, algo_filename)
    with open(algo_path, "w", encoding="utf-8") as f:
        f.write(algorithm_details)

    result = {
        "selected_columns": selected_columns,
        "w_max": float(w_max) if isinstance(w_max, (np.integer, np.floating)) else w_max,
        "correlation_file": corr_filename,
        "algorithm_file": algo_filename,
        "num_rows": int(df_processed.shape[0]),
        "num_cols": int(df_processed.shape[1]),
        "process_details": process_details,
        "correlation_details": correlation_details,
        "algorithm_details": algorithm_details,
        "graph_html": graph_html,
        "heatmap_html": heatmap_html,
        "pca_html": pca_html,
        "threshold": float(threshold),
        "params": {k: (float(v) if isinstance(v, (np.integer, np.floating)) else v) for k, v in params.items()},
        "target_column": target_column,
        "original_filename": original_filename
    }
    return result

# --- API эндпоинты ---
@app.post("/api/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(400, "Username already exists")
    hashed = get_password_hash(password)
    user = User(username=username, hashed_password=hashed, role="user")
    db.add(user)
    db.commit()
    return {"message": "User created"}

@app.post("/api/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(401, "Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}

@app.get("/api/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}

@app.get("/api/surveys")
async def list_surveys(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == "admin":
        surveys = db.query(Survey).all()
    else:
        surveys = db.query(Survey).filter(Survey.owner_id == current_user.id).all()
    return surveys

@app.get("/api/surveys/{survey_id}")
async def get_survey(survey_id: int, db: Session = Depends(get_db)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    # Возвращаем опрос со всеми вопросами и вариантами
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

@app.post("/api/surveys")
async def create_survey(survey_data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    title = survey_data.get("title")
    description = survey_data.get("description", "")
    questions_data = survey_data.get("questions", [])
    db_survey = Survey(title=title, description=description, owner_id=current_user.id)
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)
    for idx, q in enumerate(questions_data):
        db_q = Question(
            survey_id=db_survey.id,
            text=q["text"],
            question_type=q["question_type"],
            order=q.get("order", idx),
            scale_min=q.get("scale_min", 1),
            scale_max=q.get("scale_max", 10)
        )
        db.add(db_q)
        db.commit()
        db.refresh(db_q)
        if q["question_type"] in ["single", "multiple"]:
            for opt_text in q.get("options", []):
                db_opt = Option(question_id=db_q.id, text=opt_text)
                db.add(db_opt)
        db.commit()
    return {"id": db_survey.id, "message": "Survey created"}

@app.delete("/api/surveys/{survey_id}")
async def delete_survey(survey_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not allowed")
    db.delete(survey)
    db.commit()
    return {"message": "Deleted"}

@app.post("/api/surveys/{survey_id}/submit")
async def submit_response(survey_id: int, answers: dict, db: Session = Depends(get_db)):
    # Создаём запись ответа
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

@app.post("/api/surveys/{survey_id}/analyze")
async def analyze_survey(
    survey_id: int,
    params: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        raise HTTPException(404, "Survey not found")
    if survey.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not allowed")
    responses = db.query(Response).filter(Response.survey_id == survey_id).all()
    if not responses:
        raise HTTPException(400, "No responses")
    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()
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
        raise HTTPException(400, "No data after preprocessing")
    target = params.get('target_column', '')
    if target and target not in df_processed.columns:
        target = None
    _, correlation_details = apply_correlation_threshold(df_processed, params.get('threshold', 0.3))
    algo_params = {
        'n_launches': params.get('n_launches', 10),
        'n_solutions': params.get('n_solutions', 100),
        'cap': params.get('cap', 1000),
        'frac': params.get('frac', 0.35),
        'q': params.get('q', 1.0)
    }
    results = generate_results(
        df_processed, params.get('threshold', 0.3), algo_params,
        f"survey_{survey_id}", process_details, correlation_details,
        target_column=target if target else None,
        method=params.get('method', 'graph'),
        top_k=params.get('top_k', 10)
    )
    return results

@app.post("/api/analyze")
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # опционально
):
    # Сохраняем файл
    file_path, original_filename = save_upload_file(file)
    try:
        df, _, _ = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(400, f"File read error: {str(e)}")
    df_processed, process_details = preprocess_data(
        df,
        drop_first_column=drop_first,
        fill_na_with_zero=fill_na_zero,
        encode_categorical=encode_cat,
        max_categories=max_cat
    )
    if df_processed.empty:
        os.unlink(file_path)
        raise HTTPException(400, "No data after preprocessing")
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
        method=method, top_k=top_k
    )
    os.unlink(file_path)
    return results

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/octet-stream', filename=filename)
    raise HTTPException(404, "File not found")

# --- Эндпоинты для администрирования (только для admin) ---
@app.get("/api/admin/users")
async def get_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "role": u.role} for u in users]

@app.put("/api/admin/users/{user_id}/role")
async def set_user_role(user_id: int, role: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    user.role = role
    db.commit()
    return {"message": "Role updated"}