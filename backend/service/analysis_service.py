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

def generate_correlation_heatmap(correlation_matrix):
    fig = go.Figure(data=go.Heatmap(
        z=correlation_matrix.values,
        x=correlation_matrix.columns,
        y=correlation_matrix.columns,
        colorscale='RdBu',
        zmid=0,
        text=correlation_matrix.values.round(2),
        texttemplate='%{text}',
        textfont={"size": 8},
        hoverongaps=False
    ))
    fig.update_layout(
        title=None,
        xaxis_title=None,
        yaxis_title=None,
        width=1000,               # увеличиваем ширину
        height=1000,              # увеличиваем высоту
        xaxis=dict(
            tickangle=45,         # поворачиваем подписи на 45 градусов
            tickfont=dict(size=8) # уменьшаем шрифт
        ),
        yaxis=dict(
            tickfont=dict(size=8)
        )
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_correlation_graph(correlation_matrix, threshold=0.3):
    columns = correlation_matrix.columns.tolist()
    n = len(columns)
    if n < 2:
        return "<p>Недостаточно признаков для графа</p>"
    edges = []
    for i in range(n):
        for j in range(i+1, n):
            if abs(correlation_matrix.iloc[i, j]) >= threshold:
                edges.append((i, j))
    if not edges:
        return "<p>Нет связей выше порога</p>"
    import math
    angle_step = 2 * math.pi / n
    pos = {i: (math.cos(i*angle_step), math.sin(i*angle_step)) for i in range(n)}
    edge_x, edge_y = [], []
    for i, j in edges:
        x0, y0 = pos[i]; x1, y1 = pos[j]
        edge_x.extend([x0, x1, None]); edge_y.extend([y0, y1, None])
    edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.5, color='#888'), mode='lines')
    node_trace = go.Scatter(
        x=[pos[i][0] for i in range(n)], y=[pos[i][1] for i in range(n)],
        mode='markers+text', text=columns, textposition='top center',
        marker=dict(size=10, color='lightblue', line=dict(color='darkblue', width=1))
    )
    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        title=None,           # убираем заголовок
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False)
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_pca_plot(df_processed, n_components=5):
    print(f"[PCA] Размер данных: {df_processed.shape}")
    non_const_cols = [col for col in df_processed.columns if df_processed[col].std() != 0]
    if len(non_const_cols) < 2:
        return "<p>Недостаточно неконстантных признаков для PCA (нужно минимум 2).</p>"
    data = df_processed[non_const_cols]
    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data)
    rank = np.linalg.matrix_rank(data_scaled)
    print(f"[PCA] Ранг данных: {rank}, форма: {data_scaled.shape}")
    if rank < data_scaled.shape[1]:
        print("[PCA] Данные вырождены, добавляем регуляризацию")
        data_scaled += np.random.normal(0, 1e-6, data_scaled.shape)
        U, s, Vt = np.linalg.svd(data_scaled, full_matrices=False)
        s_reg = s + 1e-6
        data_scaled = U @ np.diag(s_reg) @ Vt
        print(f"[PCA] Новый ранг: {np.linalg.matrix_rank(data_scaled)}")
    n = min(n_components, data_scaled.shape[1])
    pca = PCA(n_components=n)
    pca.fit(data_scaled)
    explained_variance = pca.explained_variance_ratio_
    cumulative = np.cumsum(explained_variance)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=[f'PC{i+1}' for i in range(n)], y=explained_variance, name='Объяснённая дисперсия', marker_color='lightblue'))
    fig.add_trace(go.Scatter(x=[f'PC{i+1}' for i in range(n)], y=cumulative, name='Кумулятивная дисперсия', mode='lines+markers', marker_color='darkblue', yaxis='y2'))
    fig.update_layout(
        title='PCA: объяснённая дисперсия',
        xaxis_title='Главные компоненты',
        yaxis_title='Доля дисперсии',
        yaxis2=dict(title='Кумулятивная доля', overlaying='y', side='right'),
        hovermode='closest'
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

def generate_results(df_processed, threshold, params, original_filename, process_details, correlation_details, target_column=None, method="graph", top_k=10):
    # Приведение к числовым типам
    for col in df_processed.columns:
        df_processed[col] = pd.to_numeric(df_processed[col], errors='coerce')
    df_processed = df_processed.fillna(0)

    if target_column is not None:
        target_column = str(target_column).strip()

    # Базовое построение корреляционной матрицы (для визуализаций и графового метода)
    correlation_matrix, _ = apply_correlation_threshold(df_processed, threshold)

    # Для методов correlation и anova (если указан целевой столбец) сделаем фильтрацию признаков
    filtered = False
    if method in ('correlation', 'anova') and target_column and target_column in df_processed.columns:
        target_corr = correlation_matrix[target_column].drop(target_column, errors='ignore')
        relevant_columns = target_corr[abs(target_corr) > 0.3].index.tolist()
        if relevant_columns:
            df_filtered = df_processed[relevant_columns]
            correlation_matrix, _ = apply_correlation_threshold(df_filtered, threshold)
            filtered = True
            print(f"[Method {method}] Применена фильтрация, осталось {len(relevant_columns)} признаков")

    # Сохраняем корреляционную матрицу в CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(original_filename)[0]
    corr_filename = f"{base_name}_correlation_{timestamp}.csv"
    corr_path = os.path.join(RESULTS_DIR, corr_filename)
    correlation_matrix.to_csv(corr_path)

    # Генерируем визуализации
    heatmap_html = generate_correlation_heatmap(correlation_matrix)
    graph_html = generate_correlation_graph(correlation_matrix, threshold=0.3)
    pca_html = ""
    if method == "pca":
        pca_html = generate_pca_plot(df_processed, min(top_k, df_processed.shape[1]))

    selected_columns = []
    w_max = 0
    algorithm_details = ""

    if method == "graph":
        # Для графового метода используем всю матрицу корреляции (без фильтрации по целевому столбцу)
        column_names = list(df_processed.columns)
        Adj_w = np.abs(correlation_matrix.values.astype(float))
        w_max, xD_best, _ = do_n_launches_capped(
            Adj_w, params['n_launches'], params['n_solutions'],
            params['frac'], params['q'], params['cap'], vocal=False
        )
        selected_columns = [column_names[i] for i in xD_best.nonzero()[0] if i < len(column_names)]
        algorithm_details = f"Графовый метод\nМаксимальный вес: {w_max}\nВыбрано признаков: {len(selected_columns)}\n" + "\n".join(selected_columns)
    elif method == "correlation":
        if not target_column or target_column not in df_processed.columns:
            algorithm_details = "Ошибка: для метода корреляции необходимо указать целевой столбец (номер)."
        else:
            target = df_processed[target_column]
            features = df_processed.drop(columns=[target_column])
            corr_with_target = features.corrwith(target).abs().sort_values(ascending=False)
            selected_columns = corr_with_target.head(top_k).index.tolist()
            algorithm_details = f"Корреляция с целевым '{target_column}'\nТоп-{top_k} признаков:\n" + "\n".join(selected_columns)
    elif method == "anova":
        if not target_column or target_column not in df_processed.columns:
            algorithm_details = "Ошибка: для метода ANOVA необходимо указать целевой столбец (номер)."
        else:
            target = df_processed[target_column]
            features = df_processed.drop(columns=[target_column])
            if target.nunique() < 10:
                from sklearn.feature_selection import SelectKBest, f_classif
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
        "original_filename": original_filename
    }