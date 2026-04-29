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

def generate_correlation_heatmap(correlation_matrix):
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix.values, x=correlation_matrix.columns, y=correlation_matrix.columns,
        colorscale='RdBu', zmid=0, text=correlation_matrix.values.round(2), texttemplate='%{text}',
        textfont={"size": 8}, hoverongaps=False
    ))
    fig.update_layout(title='Матрица корреляций', xaxis_title='Признаки', yaxis_title='Признаки', width=800, height=800)
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_results(df_processed, threshold, params, original_filename, process_details, correlation_details, target_column=None, method="graph", top_k=10):
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
        from sklearn.decomposition import PCA
        n = min(top_k, df_processed.shape[1])
        pca = PCA(n_components=n)
        pca.fit(df_processed)
        explained_variance = pca.explained_variance_ratio_
        cumulative = np.cumsum(explained_variance)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[f'PC{i+1}' for i in range(n)], y=explained_variance, name='Объяснённая дисперсия', marker_color='lightblue'))
        fig.add_trace(go.Scatter(x=[f'PC{i+1}' for i in range(n)], y=cumulative, name='Кумулятивная дисперсия', mode='lines+markers', marker_color='darkblue', yaxis='y2'))
        fig.update_layout(title='PCA: объяснённая дисперсия', xaxis_title='Главные компоненты', yaxis_title='Доля дисперсии',
                          yaxis2=dict(title='Кумулятивная доля', overlaying='y', side='right'), hovermode='closest')
        pca_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

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
        "original_filename": original_filename
    }