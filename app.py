import os
import shutil
import uuid
import json
import io
import tempfile
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
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
# ДОБАВИТЬ В НАЧАЛО APP.PY НОВЫЕ ИМПОРТЫ
from fastapi.security import OAuth2PasswordRequestForm
from auth import authenticate_user, create_access_token, get_current_user, get_password_hash
# Импорты из core
from core.csv_utils import read_file_auto
from core.preprocessing import preprocess_data
from core.correlation import apply_correlation_threshold
from core.algorithm import do_n_launches_capped
from core.schemas import AnalysisParams, AnalysisResponse, FileUploadResponse
from models import User, Survey, Question, Option, Response, Answer
from auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from fastapi.security import OAuth2PasswordRequestForm
# Импорты для БД
from database import engine, Base, get_db
from models import Survey, Question, Option, Response, Answer

from fastapi.security import OAuth2PasswordRequestForm
from auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from fastapi.staticfiles import StaticFiles

# Создание таблиц БД

Base.metadata.create_all(bind=engine)
# Проверяем и добавляем колонку owner_id, если отсутствует
with engine.connect() as conn:
    # SQLite не поддерживает IF NOT EXISTS в ALTER TABLE, поэтому пробуем выполнить и игнорируем ошибку
    try:
        conn.execute("ALTER TABLE surveys ADD COLUMN owner_id INTEGER")
        conn.commit()
        print("Колонка owner_id добавлена в таблицу surveys")
    except Exception as e:
        if "duplicate column name" in str(e).lower():
            pass  # колонка уже есть
        else:
            print(f"Ошибка при добавлении колонки: {e}")
app = FastAPI(title="Survey Data Analyzer")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Кэш результатов анализа (для экспорта)
results_cache = {}  # key: task_id, value: dict

# Регистрация шрифта для кириллицы в PDF
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    FONT_NAME = 'DejaVuSans'
except:
    FONT_NAME = 'Helvetica'

def save_upload_file(upload_file: UploadFile) -> tuple[str, str]:
    file_ext = os.path.splitext(upload_file.filename)[1]
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path, upload_file.filename

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
    from sklearn.decomposition import PCA
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

def generate_pdf_report(task_id, results_cache):
    data = results_cache.get(task_id)
    if not data:
        raise ValueError("Данные не найдены")
    correlation_matrix = data['correlation_matrix']
    selected_columns = data['selected_columns']
    num_rows = data['num_rows']
    num_cols = data['num_cols']
    threshold = data['threshold']
    params = data['params']
    algorithm_details = data['algorithm_details']
    original_filename = data['original_filename']

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Russian', fontName=FONT_NAME, fontSize=10, leading=14))
    story = []

    title_style = ParagraphStyle(name='Title', fontName=FONT_NAME, fontSize=16, leading=20, alignment=1)
    story.append(Paragraph(f"Отчёт по анализу данных: {original_filename}", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Russian']))
    story.append(Paragraph(f"Размер данных: {num_rows} строк, {num_cols} столбцов", styles['Russian']))
    story.append(Paragraph(f"Порог корреляции: {threshold}", styles['Russian']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Выбранные столбцы:", styles['Heading2']))
    selected_text = ", ".join(selected_columns[:20])
    if len(selected_columns) > 20:
        selected_text += f" ... и ещё {len(selected_columns)-20}"
    story.append(Paragraph(selected_text, styles['Russian']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Матрица корреляций (первые 10 признаков):", styles['Heading2']))
    corr_subset = correlation_matrix.iloc[:10, :10]
    data_table = [corr_subset.columns.tolist()] + corr_subset.values.tolist()
    t = Table(data_table)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Тепловая карта как изображение
    try:
        fig = go.Figure(data=go.Heatmap(z=correlation_matrix.values, x=correlation_matrix.columns, y=correlation_matrix.columns, colorscale='RdBu', zmid=0))
        fig.update_layout(width=500, height=500)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.write_image(tmp.name, format='png')
            story.append(Image(tmp.name, width=4*inch, height=4*inch))
            os.unlink(tmp.name)
    except:
        story.append(Paragraph("Не удалось встроить график корреляций", styles['Russian']))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Детали работы алгоритма:", styles['Heading2']))
    details_para = algorithm_details.replace('\n', '<br/>')
    story.append(Paragraph(details_para, styles['Russian']))

    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_excel_report(task_id, results_cache):
    data = results_cache.get(task_id)
    if not data:
        raise ValueError("Данные не найдены")
    correlation_matrix = data['correlation_matrix']
    selected_columns = data['selected_columns']
    df_processed = data['df_processed']
    process_details = data['process_details']
    correlation_details = data['correlation_details']
    algorithm_details = data['algorithm_details']
    params = data['params']

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        pd.DataFrame({'Выбранные столбцы': selected_columns}).to_excel(writer, sheet_name='Выбранные столбцы', index=False)
        correlation_matrix.to_excel(writer, sheet_name='Корреляция')
        df_processed.head(100).to_excel(writer, sheet_name='Данные (первые 100)', index=False)
        details_df = pd.DataFrame({'Этап': ['Предобработка', 'Корреляция', 'Алгоритм'], 'Детали': [process_details, correlation_details, algorithm_details]})
        details_df.to_excel(writer, sheet_name='Детали', index=False)
        params_df = pd.DataFrame({'Параметр': list(params.keys()), 'Значение': list(params.values())})
        params_df.to_excel(writer, sheet_name='Параметры', index=False)
    output.seek(0)
    return output

def generate_results(df_processed, threshold, params, original_filename, process_details, correlation_details,
                     target_column=None, method="graph", top_k=10):
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
            print("Ошибка в алгоритме:")
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
        "graph_html": graph_html,
        "heatmap_html": heatmap_html,
        "pca_html": pca_html,
        "correlation_matrix": correlation_matrix,
        "df_processed": df_processed,
        "threshold": threshold,
        "params": params,
        "target_column": target_column,
        "original_filename": original_filename
    }
def generate_survey_stats(survey_id: int, db: Session):
    """Генерирует статистику по опросу: для single – варианты и проценты, для scale – среднее/медиана, для text – список ответов."""
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    if not survey:
        return None
    questions = db.query(Question).filter(Question.survey_id == survey_id).order_by(Question.order).all()
    stats = []
    for q in questions:
        answers = db.query(Answer).filter(Answer.question_id == q.id).all()
        total = len(answers)
        if q.question_type == 'single':
            options = db.query(Option).filter(Option.question_id == q.id).all()
            opt_counts = {opt.id: 0 for opt in options}
            for a in answers:
                if a.option_id and a.option_id in opt_counts:
                    opt_counts[a.option_id] += 1
            stats.append({
                'question_text': q.text,
                'question_type': 'single',
                'options': [
                    {
                        'text': opt.text,
                        'count': opt_counts[opt.id],
                        'percent': (opt_counts[opt.id] / total * 100) if total else 0
                    }
                    for opt in options
                ]
            })
        elif q.question_type == 'scale':
            values = [a.numeric_value for a in answers if a.numeric_value is not None]
            mean_val = np.mean(values) if values else None
            median_val = np.median(values) if values else None
            stats.append({
                'question_text': q.text,
                'question_type': 'scale',
                'min': q.scale_min,
                'max': q.scale_max,
                'mean': mean_val,
                'median': median_val,
                'distribution': {int(v): values.count(v) for v in set(values)} if values else {}
            })
        else:  # text
            text_answers = [a.text_value for a in answers if a.text_value]
            stats.append({
                'question_text': q.text,
                'question_type': 'text',
                'answers': text_answers
            })
    return stats
def generate_pdf_stats_report(survey, stats):
    """Генерирует PDF-отчёт со статистикой опроса (проценты, голоса, графики)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    import tempfile
    import plotly.graph_objects as go
    import plotly.io as pio

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    # Добавляем стиль для кириллицы (если не зарегистрирован шрифт, используем Helvetica)
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
        font_name = 'DejaVuSans'
    except:
        font_name = 'Helvetica'
    styles.add(ParagraphStyle(name='Russian', fontName=font_name, fontSize=10, leading=14))
    title_style = ParagraphStyle(name='Title', fontName=font_name, fontSize=16, leading=20, alignment=1)

    story = []
    story.append(Paragraph(f"Статистика опроса: {survey.title}", title_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Описание: {survey.description or ''}", styles['Russian']))
    story.append(Paragraph(f"Дата создания: {survey.created_at.strftime('%d.%m.%Y %H:%M')}", styles['Russian']))
    story.append(Spacer(1, 12))

    for q_stat in stats:
        story.append(Paragraph(f"<b>{q_stat['question_text']}</b>", styles['Heading2']))
        if q_stat['question_type'] == 'single':
            data = [['Вариант', 'Голосов', 'Процент']]
            for opt in q_stat['options']:
                data.append([opt['text'], opt['count'], f"{opt['percent']:.1f}%"])
            t = Table(data)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,-1), font_name),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            story.append(t)
            # Круговая диаграмма через Plotly -> PNG
            try:
                fig = go.Figure(data=[go.Pie(labels=[opt['text'] for opt in q_stat['options']],
                                             values=[opt['count'] for opt in q_stat['options']])])
                fig.update_layout(title="Распределение ответов")
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    fig.write_image(tmp.name, format='png')
                    story.append(Image(tmp.name, width=4*inch, height=3*inch))
                    os.unlink(tmp.name)
            except:
                story.append(Paragraph("(не удалось построить график)", styles['Russian']))
        elif q_stat['question_type'] == 'scale':
            story.append(Paragraph(f"Минимум: {q_stat['min']}, Максимум: {q_stat['max']}", styles['Russian']))
            story.append(Paragraph(f"Среднее: {q_stat['mean']:.2f} (если есть данные)", styles['Russian']))
            story.append(Paragraph(f"Медиана: {q_stat['median']:.2f}", styles['Russian']))
            if q_stat['distribution']:
                data = [['Оценка', 'Количество']] + [[k, v] for k, v in q_stat['distribution'].items()]
                t = Table(data)
                t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.black)]))
                story.append(t)
        else:  # text
            story.append(Paragraph("Текстовые ответы (первые 10):", styles['Russian']))
            for ans in q_stat['answers'][:10]:
                story.append(Paragraph(f"- {ans}", styles['Russian']))
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)
    return buffer
def generate_results_excel(survey, stats):
    """Генерирует Excel-файл в формате: вопрос, варианты, проценты, число голосов."""
    output = io.BytesIO()
    rows = []
    for q_stat in stats:
        rows.append([q_stat['question_text'], "", "", ""])  # строка вопроса
        if q_stat['question_type'] == 'single':
            for opt in q_stat['options']:
                rows.append(["", opt['text'], f"{opt['percent']:.1f}%", opt['count']])
        elif q_stat['question_type'] == 'scale':
            rows.append(["", f"Среднее: {q_stat['mean']:.2f}", "", ""])
            rows.append(["", f"Медиана: {q_stat['median']:.2f}", "", ""])
            rows.append(["", "Распределение:", "", ""])
            for val, cnt in q_stat['distribution'].items():
                rows.append(["", f"{val}", f"{(cnt/len(q_stat['answers'])*100):.1f}%", cnt])
        else:
            rows.append(["", "Текстовые ответы (первые 20):", "", ""])
            for ans in q_stat['answers'][:20]:
                rows.append(["", ans, "", ""])
        rows.append(["", "", "", ""])  # разделитель между вопросами
    df = pd.DataFrame(rows, columns=['Вопрос', 'Варианты ответа', 'Проценты', 'Число голосов'])
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Результаты', index=False)
    output.seek(0)
    return output
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
    target_column: str = Form(""),
    method: str = Form("graph"),
    top_k: int = Form(10)
):
    if not (0.0 <= threshold <= 1.0):
        return templates.TemplateResponse("index.html", {"request": request, "error": "Порог корреляции должен быть от 0.0 до 1.0"})

    try:
        file_path, original_filename = save_upload_file(file)
    except Exception as e:
        return templates.TemplateResponse("index.html", {"request": request, "error": f"Ошибка сохранения файла: {str(e)}"})

    try:
        df, _, _ = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        os.unlink(file_path)
        return templates.TemplateResponse("index.html", {"request": request, "error": f"Ошибка чтения файла: {str(e)}"})

    try:
        df_processed, process_details = preprocess_data(
            df, drop_first_column=drop_first, fill_na_with_zero=fill_na_zero,
            encode_categorical=encode_cat, max_categories=max_cat
        )
        if df_processed.empty:
            raise ValueError("После предобработки не осталось данных")
    except Exception as e:
        os.unlink(file_path)
        return templates.TemplateResponse("index.html", {"request": request, "error": f"Ошибка предобработки: {str(e)}"})

    target_column = str(target_column).strip() if target_column else ""
    if target_column and target_column not in df_processed.columns:
        warning = f"Столбец '{target_column}' не найден после предобработки. Фильтрация по целевому признаку не применялась."
        target_column = None
    else:
        warning = None

    _, correlation_details = apply_correlation_threshold(df_processed, threshold)
    params_dict = {"n_launches": n_launches, "n_solutions": n_solutions, "cap": cap, "frac": frac, "q": q}
    try:
        results = generate_results(
            df_processed, threshold, params_dict, original_filename, process_details, correlation_details,
            target_column=target_column if target_column else None, method=method, top_k=top_k
        )
    except Exception as e:
        os.unlink(file_path)
        return templates.TemplateResponse("index.html", {"request": request, "error": f"Ошибка анализа: {str(e)}"})

    os.unlink(file_path)

    # Сохраняем результаты в кэш
    task_id = str(uuid.uuid4())
    results_cache[task_id] = {
        "correlation_matrix": results["correlation_matrix"],
        "df_processed": results["df_processed"],
        "selected_columns": results["selected_columns"],
        "num_rows": results["num_rows"],
        "num_cols": results["num_cols"],
        "threshold": threshold,
        "params": params_dict,
        "algorithm_details": results["algorithm_details"],
        "process_details": process_details,
        "correlation_details": correlation_details,
        "original_filename": original_filename
    }

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
        "params": params_dict,
        "drop_first": drop_first,
        "fill_na_zero": fill_na_zero,
        "encode_cat": encode_cat,
        "max_cat": max_cat,
        "target_column": target_column,
        "method": method,
        "top_k": top_k,
        "warning": warning,
        "process_details": results["process_details"],
        "correlation_details": results["correlation_details"],
        "algorithm_details": results["algorithm_details"],
        "graph_html": results["graph_html"],
        "heatmap_html": results["heatmap_html"],
        "pca_html": results["pca_html"],
        "task_id": task_id
    })

# -------------------- ЭКСПОРТ --------------------
@app.post("/export/pdf")
async def export_pdf(task_id: str = Form(...)):
    try:
        pdf_buffer = generate_pdf_report(task_id, results_cache)
        return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=report.pdf"})
    except Exception as e:
        return {"error": str(e)}

@app.post("/export/excel")
async def export_excel(task_id: str = Form(...)):
    try:
        excel_buffer = generate_excel_report(task_id, results_cache)
        return StreamingResponse(excel_buffer, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": "attachment; filename=report.xlsx"})
    except Exception as e:
        return {"error": str(e)}

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
    target_column: str = Form(""),
    method: str = Form("graph"),
    top_k: int = Form(10)
):
    if not (0.0 <= threshold <= 1.0):
        raise HTTPException(status_code=400, detail="Порог корреляции должен быть от 0.0 до 1.0")
    try:
        file_path, original_filename = save_upload_file(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения файла: {str(e)}")
    try:
        df, _, _ = read_file_auto(file_path, max_rows=None)
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {str(e)}")
    try:
        df_processed, process_details = preprocess_data(
            df, drop_first_column=drop_first, fill_na_with_zero=fill_na_zero,
            encode_categorical=encode_cat, max_categories=max_cat
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
    params_dict = {"n_launches": n_launches, "n_solutions": n_solutions, "cap": cap, "frac": frac, "q": q}
    try:
        results = generate_results(
            df_processed, threshold, params_dict, original_filename, process_details, correlation_details,
            target_column=target_column if target_column else None, method=method, top_k=top_k
        )
    except Exception as e:
        os.unlink(file_path)
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")
    os.unlink(file_path)
    results["target_column"] = target_column if target_column else ""
    results["method"] = method
    return AnalysisResponse(**results)

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(RESULTS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/octet-stream', filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

# -------------------- ОПРОСЫ (без изменений) --------------------
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
    return templates.TemplateResponse("survey_results.html", {"request": request, "survey": survey, "responses_count": responses_count})

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
    target_column: str = Form(""),
    method: str = Form("graph"),
    top_k: int = Form(10)
):
    target_column = str(target_column).strip() if target_column else ""
    responses = db.query(Response).filter(Response.survey_id == survey_id).all()
    if not responses:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {"request": request, "survey": survey, "responses_count": 0, "error": "Нет данных для анализа"})
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
    if df.empty:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {"request": request, "survey": survey, "responses_count": len(responses), "error": "Не удалось сформировать DataFrame из ответов"})
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
        return templates.TemplateResponse("survey_results.html", {"request": request, "survey": survey, "responses_count": len(responses), "error": f"Ошибка предобработки: {str(e)}"})
    if df_processed.empty:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {"request": request, "survey": survey, "responses_count": len(responses), "error": "После предобработки не осталось данных"})
    if target_column and target_column not in df_processed.columns:
        target_column = None
    _, correlation_details = apply_correlation_threshold(df_processed, threshold)
    params = {"n_launches": n_launches, "n_solutions": n_solutions, "cap": cap, "frac": frac, "q": q}
    try:
        results = generate_results(
            df_processed, threshold, params, f"survey_{survey_id}",
            process_details, correlation_details,
            target_column=target_column if target_column else None,
            method=method, top_k=top_k
        )
    except Exception as e:
        survey = db.query(Survey).filter(Survey.id == survey_id).first()
        return templates.TemplateResponse("survey_results.html", {"request": request, "survey": survey, "responses_count": len(responses), "error": f"Ошибка анализа: {str(e)}"})
    survey = db.query(Survey).filter(Survey.id == survey_id).first()
    return templates.TemplateResponse("survey_results.html", {
        "request": request,
        "survey": survey,
        "responses_count": len(responses),
        "results": results,
        "target_column": target_column,
        "method": method,
        "top_k": top_k
    })

# ==================== АУТЕНТИФИКАЦИЯ ====================
@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed = get_password_hash(password)
    user = User(username=username, hashed_password=hashed)
    db.add(user)
    db.commit()
    return {"message": "User created"}

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/logout")
async def logout():
    # В реальном приложении нужно очистить токен (используйте зависимость)
    return RedirectResponse(url="/", status_code=303)
# ==================== ОПРОСЫ С АУТЕНТИФИКАЦИЕЙ ====================
@app.get("/surveys")
async def list_surveys(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    surveys = db.query(Survey).filter(Survey.owner_id == current_user.id).order_by(Survey.created_at.desc()).all()
    return templates.TemplateResponse("surveys_list.html", {"request": request, "surveys": surveys})

@app.get("/surveys/new", response_class=HTMLResponse)
async def create_survey_form(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("create_survey.html", {"request": request})

@app.post("/api/surveys", response_class=RedirectResponse)
async def create_survey_api(
    survey_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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

    return RedirectResponse(url=f"/surveys/{db_survey.id}", status_code=303)

@app.get("/surveys/{survey_id}/results")
async def survey_results(
    request: Request,
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.owner_id == current_user.id).first()
    if not survey:
        return HTMLResponse("Опрос не найден или нет доступа", status_code=404)
    responses_count = db.query(Response).filter(Response.survey_id == survey_id).count()
    stats = generate_survey_stats(survey_id, db)  # функция описана ранее
    return templates.TemplateResponse("survey_results.html", {
        "request": request,
        "survey": survey,
        "responses_count": responses_count,
        "stats": stats
    })

# ==================== ЭКСПОРТ СТАТИСТИКИ И РЕЗУЛЬТАТОВ ====================
@app.get("/surveys/{survey_id}/export/stats")
async def export_survey_stats_pdf(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.owner_id == current_user.id).first()
    if not survey:
        raise HTTPException(404, "Опрос не найден")
    stats = generate_survey_stats(survey_id, db)
    # Генерация PDF (используйте generate_pdf_stats_report)
    pdf_buffer = generate_pdf_stats_report(survey, stats)
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=survey_{survey_id}_stats.pdf"})

@app.get("/surveys/{survey_id}/export/results")
async def export_survey_results_excel(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.owner_id == current_user.id).first()
    if not survey:
        raise HTTPException(404, "Опрос не найден")
    stats = generate_survey_stats(survey_id, db)
    output = generate_results_excel(survey, stats)
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f"attachment; filename=survey_{survey_id}_results.xlsx"})
@app.get("/surveys/new", response_class=HTMLResponse)
async def create_survey_form(request: Request, current_user: User = Depends(get_current_user)):
    return templates.TemplateResponse("create_survey.html", {"request": request})

@app.post("/api/surveys", response_class=RedirectResponse)
async def create_survey_api(
    survey_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
    return RedirectResponse(url=f"/surveys/{db_survey.id}", status_code=303)

@app.post("/surveys/{survey_id}/delete")
async def delete_survey(
    survey_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(Survey).filter(Survey.id == survey_id, Survey.owner_id == current_user.id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="Опрос не найден или нет доступа")
    db.delete(survey)
    db.commit()
    return RedirectResponse(url="/surveys", status_code=303)
# ==================== ИМПОРТ ОПРОСА (3 формата) ====================
@app.post("/surveys/import")
async def import_survey(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()
    content = await file.read()

    if ext == '.json':
        data = json.loads(content)
        survey_data = parse_json_import(data)
    elif ext == '.csv':
        df = pd.read_csv(io.BytesIO(content))
        survey_data = parse_csv_import(df)
    elif ext in ['.xls', '.xlsx']:
        df = pd.read_excel(io.BytesIO(content))
        survey_data = parse_excel_import(df)
    else:
        raise HTTPException(400, "Неподдерживаемый формат. Используйте JSON, CSV или Excel")

    db_survey = Survey(title=survey_data["title"], description=survey_data.get("description", ""), owner_id=current_user.id)
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)

    for idx, q in enumerate(survey_data["questions"]):
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

    return RedirectResponse(url=f"/surveys/{db_survey.id}", status_code=303)

# Функции парсеров (вставить в app.py)
def parse_json_import(data):
    return {
        "title": data.get("title", "Импортированный опрос"),
        "description": data.get("description", ""),
        "questions": [
            {
                "text": q["text"],
                "question_type": q["type"],
                "order": idx,
                "options": q.get("options", []),
                "scale_min": q.get("min", 1),
                "scale_max": q.get("max", 10)
            }
            for idx, q in enumerate(data.get("questions", []))
        ]
    }

def parse_csv_import(df):
    questions = []
    for idx, row in df.iterrows():
        q_type = str(row.get("type", "text")).strip()
        opts = []
        if q_type in ["single", "multiple"] and pd.notna(row.get("options")):
            opts = [o.strip() for o in str(row["options"]).split(";") if o.strip()]
        questions.append({
            "text": str(row.get("text", "")),
            "question_type": q_type,
            "order": idx,
            "options": opts,
            "scale_min": int(row.get("scale_min", 1)) if pd.notna(row.get("scale_min")) else 1,
            "scale_max": int(row.get("scale_max", 10)) if pd.notna(row.get("scale_max")) else 10
        })
    return {"title": "Импортированный опрос", "description": "", "questions": questions}

def parse_excel_import(df):
    return parse_csv_import(df)