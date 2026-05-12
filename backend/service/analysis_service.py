import os
import uuid
import math
import numpy as np
import pandas as pd
from datetime import datetime
from core.csv_utils import read_file_auto
from core.preprocessing import preprocess_data
from core.correlation import apply_correlation_threshold
from core.algorithm import do_n_launches_capped
import plotly.graph_objects as go
import plotly.io as pio
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.feature_selection import SelectKBest, f_classif, f_regression
import io
import tempfile

# PDF generation imports
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Определяем директорию, где находится текущий файл
current_dir = os.path.dirname(os.path.abspath(__file__))
arial_path = os.path.join(current_dir, 'arial.ttf')

if os.path.exists(arial_path):
    pdfmetrics.registerFont(TTFont('Arial', arial_path))
    DEFAULT_FONT = 'Arial'
else:
    DEFAULT_FONT = 'Helvetica'   # fallback

# ---------- Конфигурация папок ----------
UPLOAD_DIR = "uploads"
RESULTS_DIR = "results"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

def save_upload_file(upload_file):
    file_ext = os.path.splitext(upload_file.filename)[1]
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as buffer:
        buffer.write(upload_file.file.read())
    return file_path, upload_file.filename

def generate_correlation_graph(correlation_matrix, threshold=0.3):
    columns = correlation_matrix.columns.tolist()
    n = len(columns)
    if n == 0:
        return "<p>Недостаточно данных для построения графа</p>"
    edges = []
    for i in range(n):
        for j in range(i+1, n):
            corr = correlation_matrix.iloc[i, j]
            if abs(corr) >= threshold:
                edges.append((i, j, corr))
    if not edges:
        return "<p>Нет связей с корреляцией выше порога</p>"
    angle_step = 2 * math.pi / n
    pos = {i: (math.cos(i*angle_step), math.sin(i*angle_step)) for i in range(n)}
    edge_x, edge_y = [], []
    for i, j, corr in edges:
        x0, y0 = pos[i]; x1, y1 = pos[j]
        edge_x.extend([x0, x1, None]); edge_y.extend([y0, y1, None])
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

def generate_correlation_heatmap(correlation_matrix, max_cols=30):
    # Если признаков больше max_cols, показываем только первые max_cols
    if correlation_matrix.shape[1] > max_cols:
        corr_subset = correlation_matrix.iloc[:max_cols, :max_cols]
        print(f"[Heatmap] Ограничено отображение {corr_subset.shape[1]} признаков из {correlation_matrix.shape[1]}")
    else:
        corr_subset = correlation_matrix

    fig = go.Figure(data=go.Heatmap(
        z=corr_subset.values,
        x=corr_subset.columns,
        y=corr_subset.columns,
        colorscale='RdBu',
        zmid=0,
        text=corr_subset.values.round(2),
        texttemplate='%{text}',
        textfont={"size": 8},
        hoverongaps=False
    ))
    fig.update_layout(
        title=None,
        xaxis_title=None,
        yaxis_title=None,
        width=1000,
        height=1000,
        xaxis=dict(
            tickangle=45,
            tickfont=dict(size=7),
            nticks=30 if corr_subset.shape[1] > 30 else corr_subset.shape[1]
        ),
        yaxis=dict(
            tickfont=dict(size=7),
            nticks=30 if corr_subset.shape[1] > 30 else corr_subset.shape[1]
        )
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_pca_plot(df_processed, n_components=5):
    non_const_cols = [col for col in df_processed.columns if df_processed[col].std() != 0]
    if len(non_const_cols) < 2:
        return "<p>Недостаточно неконстантных признаков для PCA</p>"
    data = df_processed[non_const_cols]
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data)
    rank = np.linalg.matrix_rank(data_scaled)
    if rank < data_scaled.shape[1]:
        data_scaled += np.random.normal(0, 1e-6, data_scaled.shape)
        U, s, Vt = np.linalg.svd(data_scaled, full_matrices=False)
        s_reg = s + 1e-6
        data_scaled = U @ np.diag(s_reg) @ Vt
    n = min(n_components, data_scaled.shape[1])
    pca = PCA(n_components=n)
    pca.fit(data_scaled)
    explained_variance = pca.explained_variance_ratio_
    cumulative = np.cumsum(explained_variance)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[f'PC{i+1}' for i in range(n)], y=explained_variance, name='Объяснённая дисперсия', marker_color='lightblue'))
    fig.add_trace(go.Scatter(x=[f'PC{i+1}' for i in range(n)], y=cumulative, name='Кумулятивная дисперсия', mode='lines+markers', marker_color='darkblue', yaxis='y2'))
    fig.update_layout(
        title=None,
        xaxis_title='Главные компоненты',
        yaxis_title='Доля дисперсии',
        yaxis2=dict(title='Кумулятивная доля', overlaying='y', side='right'),
        hovermode='closest'
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_results(df_processed, threshold, params, original_filename, process_details, correlation_details, target_column=None, method="graph", top_k=10):
    for col in df_processed.columns:
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
    df_processed = df_processed.fillna(0)

    if target_column is not None:
        target_column = str(target_column).strip()
    correlation_matrix, _ = apply_correlation_threshold(df_processed, threshold)

    filtered = False
    if method in ('correlation', 'anova') and target_column and target_column in df_processed.columns:
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
    if method == "pca":
        pca_html = generate_pca_plot(df_processed, min(top_k, df_processed.shape[1]))

    selected_columns = []
    w_max = 0
    algorithm_details = ""

    if method == "graph":
        column_names = list(df_processed.columns if not filtered else df_filtered.columns)
        Adj_w = np.abs(correlation_matrix.values.astype(float))
        w_max, xD_best, _ = do_n_launches_capped(
            Adj_w, params['n_launches'], params['n_solutions'],
            params['frac'], params['q'], params['cap'], vocal=False
        )
        selected_columns = [column_names[i] for i in xD_best.nonzero()[0] if i < len(column_names)]
        algorithm_details = f"Графовый метод\nМаксимальный вес: {w_max}\nВыбрано признаков: {len(selected_columns)}\n" + "\n".join(selected_columns)
    elif method == "correlation":
        if not target_column or target_column not in df_processed.columns:
            algorithm_details = "Ошибка: для метода корреляции необходимо указать целевой столбец."
        else:
            target = df_processed[target_column]
            features = df_processed.drop(columns=[target_column])
            corr_with_target = features.corrwith(target).abs().sort_values(ascending=False)
            selected_columns = corr_with_target.head(top_k).index.tolist()
            algorithm_details = f"Корреляция с целевым '{target_column}'\nТоп-{top_k} признаков:\n" + "\n".join(selected_columns)
    elif method == "anova":
        if not target_column or target_column not in df_processed.columns:
            algorithm_details = "Ошибка: для метода ANOVA необходимо указать целевой столбец."
        else:
            target = df_processed[target_column]
            features = df_processed.drop(columns=[target_column])
            if target.nunique() < 10:
                selector = SelectKBest(f_classif, k=min(top_k, features.shape[1]))
                selector.fit(features, target)
                selected_idx = selector.get_support(indices=True)
                selected_columns = [features.columns[i] for i in selected_idx]
                algorithm_details = f"ANOVA (F-тест) с целевым '{target_column}'\nТоп-{top_k} признаков:\n" + "\n".join(selected_columns)
            else:
                algorithm_details = f"ANOVA: целевая переменная '{target_column}' имеет {target.nunique()} уникальных значений, требуется категориальная (<10)."
    elif method == "pca":
        algorithm_details = "PCA не отбирает исходные признаки, а показывает объяснённую дисперсию. См. график выше."
    else:
        algorithm_details = f"Неизвестный метод: {method}. Доступны: graph, correlation, anova, pca."

    algo_filename = f"{base_name}_algorithm_{timestamp}.txt"
    algo_path = os.path.join(RESULTS_DIR, algo_filename)
    with open(algo_path, "w", encoding="utf-8") as f:
        f.write(algorithm_details)

    return {
        "selected_columns": selected_columns,
        "w_max": float(w_max),
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
        "params": {k: float(v) if isinstance(v, (np.integer, np.floating)) else v for k, v in params.items()},
        "target_column": target_column,
        "original_filename": original_filename,
        "method": method
    }

def generate_pdf_report_from_df(results, df_processed):
    """Генерирует PDF-отчёт с графиками, таблицами и поддержкой кириллицы."""
    with tempfile.TemporaryDirectory() as tmpdir:
        corr_file = results.get('correlation_file')
        heatmap_path = None
        graph_path = None

        if corr_file:
            corr_path = os.path.join(RESULTS_DIR, corr_file)
            corr_df = pd.read_csv(corr_path, index_col=0)

            # Тепловая карта
            fig_heat = go.Figure(data=go.Heatmap(
                z=corr_df.values,
                x=corr_df.columns,
                y=corr_df.columns,
                colorscale='RdBu',
                zmid=0
            ))
            fig_heat.update_layout(title=None, width=600, height=600)
            heatmap_path = os.path.join(tmpdir, 'heatmap.png')
            fig_heat.write_image(heatmap_path, format='png')

            # Граф корреляций (круговой)
            columns = corr_df.columns.tolist()
            n = len(columns)
            edges = []
            threshold = results.get('threshold', 0.3)
            for i in range(n):
                for j in range(i+1, n):
                    if abs(corr_df.iloc[i, j]) >= threshold:
                        edges.append((i, j))
            if edges:
                angle_step = 2 * math.pi / n
                pos = {i: (math.cos(i*angle_step), math.sin(i*angle_step)) for i in range(n)}
                edge_x, edge_y = [], []
                for i, j in edges:
                    x0, y0 = pos[i]; x1, y1 = pos[j]
                    edge_x.extend([x0, x1, None]); edge_y.extend([y0, y1, None])
                edge_trace = go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(color='gray'))
                node_trace = go.Scatter(
                    x=[pos[i][0] for i in range(n)], y=[pos[i][1] for i in range(n)],
                    mode='markers+text', text=columns, textposition='top center',
                    marker=dict(size=8, color='lightblue')
                )
                fig_graph = go.Figure(data=[edge_trace, node_trace])
                fig_graph.update_layout(title=None, showlegend=False, width=600, height=600,
                                        xaxis=dict(visible=False), yaxis=dict(visible=False))
                graph_path = os.path.join(tmpdir, 'graph.png')
                fig_graph.write_image(graph_path, format='png')

        # Сборка PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                                rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        # Применяем шрифт Arial (или fallback)
        for style_name in styles.byName:
            styles[style_name].fontName = DEFAULT_FONT

        story = []

        # Заголовок
        story.append(Paragraph("Отчёт по анализу данных", styles['Title']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"Файл: {results.get('original_filename', 'неизвестен')}", styles['Normal']))
        story.append(Paragraph(f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 12))

        # Параметры
        story.append(Paragraph("Параметры анализа:", styles['Heading2']))
        story.append(Paragraph(f"Метод: {results.get('method', 'graph')}", styles['Normal']))
        story.append(Paragraph(f"Порог корреляции: {results.get('threshold', 0.3)}", styles['Normal']))
        params_dict = results.get('params', {})
        story.append(Paragraph(f"Запусков: {params_dict.get('n_launches', '?')}, решений: {params_dict.get('n_solutions', '?')}", styles['Normal']))
        story.append(Spacer(1, 12))

        # Выбранные признаки
        story.append(Paragraph("Выбранные признаки:", styles['Heading2']))
        for col in results.get('selected_columns', [])[:20]:
            story.append(Paragraph(f"- {col}", styles['Normal']))
        if len(results.get('selected_columns', [])) > 20:
            story.append(Paragraph(f"... и ещё {len(results.get('selected_columns', []))-20} признаков", styles['Normal']))
        story.append(Spacer(1, 12))

        # Матрица корреляции (фрагмент 10x10)
        story.append(Paragraph("Матрица корреляции (фрагмент 10×10):", styles['Heading2']))
        try:
            corr_df_loc = pd.read_csv(os.path.join(RESULTS_DIR, results['correlation_file']), index_col=0)
            sub = corr_df_loc.iloc[:10, :10]
            data_table = [sub.columns.tolist()] + sub.values.tolist()
            t = Table(data_table)
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTSIZE', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ]))
            story.append(t)
        except Exception as e:
            story.append(Paragraph(f"Матрица недоступна: {str(e)}", styles['Normal']))
        story.append(Spacer(1, 12))

        # Тепловая карта
        if heatmap_path:
            story.append(Paragraph("Тепловая карта корреляций:", styles['Heading2']))
            story.append(Image(heatmap_path, width=6*inch, height=6*inch))
            story.append(Spacer(1, 12))

        # Граф корреляций
        if graph_path:
            story.append(Paragraph("Граф корреляций:", styles['Heading2']))
            story.append(Image(graph_path, width=6*inch, height=6*inch))
            story.append(Spacer(1, 12))

        doc.build(story)
        buffer.seek(0)
        return buffer