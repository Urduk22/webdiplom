import pandas as pd
import re
import numpy as np

def clean_column_names(df):
    original_columns = df.columns.tolist()
    clean_columns = []

    for col in df.columns:
        col_str = str(col)
        col_clean = col_str.strip()
        col_clean = col_clean.replace(' ', '_')
        col_clean = re.sub(r'[^a-zA-Z0-9_]', '', col_clean)
        col_clean = col_clean.lower()
        if not col_clean:
            col_clean = f"column_{original_columns.index(col)}"
        clean_columns.append(col_clean)

    final_columns = []
    seen = {}
    for col in clean_columns:
        if col in seen:
            seen[col] += 1
            final_columns.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 1
            final_columns.append(col)

    df_clean = df.copy()
    df_clean.columns = final_columns
    return df_clean, original_columns, final_columns

def convert_comma_to_dot(value):
    if isinstance(value, str):
        return value.replace(',', '.').replace('"', '').replace("'", "")
    return value

def preprocess_data(df, drop_first_column=False, fill_na_with_zero=True,
                    encode_categorical=False, max_categories=10):
    """
    Предобработка данных:
    - очистка имён столбцов
    - удаление первого столбца (опционально)
    - замена запятых на точки в строковых значениях
    - удаление столбцов с >30% пустых значений
    - обработка пропусков (замена нулями или удаление строк)
    - кодирование категориальных столбцов методом One-Hot Encoding, если число уникальных значений <= max_categories
    - преобразование всех столбцов в числовой тип
    """
    original_shape = df.shape
    df, original_columns, final_columns = clean_column_names(df)

    if drop_first_column and len(df.columns) > 0:
        first_column_name = df.columns[0]
        df = df.drop(columns=[first_column_name])
        final_columns = final_columns[1:] if len(final_columns) > 1 else []
        if len(df.columns) == 0:
            return pd.DataFrame(), "После удаления первого столбца не осталось данных"

    for column in df.columns:
        df[column] = df[column].apply(convert_comma_to_dot)

    # Удаление столбцов с >30% пустых значений
    columns_to_drop = []
    for column in df.columns:
        empty_count = df[column].isna().sum() + (df[column].astype(str).str.strip() == '').sum()
        total_count = len(df[column])
        empty_percentage = (empty_count / total_count) * 100 if total_count > 0 else 100

        if empty_percentage > 30:
            columns_to_drop.append(column)

    if columns_to_drop:
        df = df.drop(columns=columns_to_drop)
        print(f"Удалено столбцов с >30% пустых значений: {len(columns_to_drop)}")
        print(f"Удаленные столбцы: {columns_to_drop}")

    if len(df.columns) == 0:
        return pd.DataFrame(), "После удаления столбцов с пустыми значениями не осталось данных"

    # Обработка пропусков
    if fill_na_with_zero:
        print("  Заполняем пропуски нулями...")
        df = df.fillna(0)
        rows_removed = 0
    else:
        print("  Удаляем строки с пропусками...")
        df_clean = df.dropna()
        rows_removed = original_shape[0] - df_clean.shape[0]
        df = df_clean

    # ---- One-Hot Encoding для категориальных столбцов ----
    encoded_summary = []
    if encode_categorical:
        print(f"  Кодирование категориальных столбцов методом One-Hot (макс. уникальных = {max_categories})...")
        cols_to_encode = []
        encode_info = []

        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str)
                unique_vals = df[col].nunique()
                if unique_vals <= max_categories:
                    cols_to_encode.append(col)
                    encode_info.append((col, unique_vals))
                else:
                    print(f"    Столбец '{col}' пропущен: {unique_vals} уникальных значений > {max_categories}")

        if cols_to_encode:
            df = pd.get_dummies(df, columns=cols_to_encode, prefix_sep='_', drop_first=False, dtype=int)
            for col, uv in encode_info:
                new_cols = [c for c in df.columns if c.startswith(col + '_')]
                encoded_summary.append((col, uv, new_cols))
                print(f"    Столбец '{col}' закодирован -> {len(new_cols)} бинарных столбцов ({uv} уникальных)")
        else:
            print("    Нет категориальных столбцов для кодирования")
    # -------------------------------------------------------

    # Преобразование в числовой тип
    numeric_columns = []
    non_numeric_columns = []

    for column in df.columns:
        try:
            df[column] = pd.to_numeric(df[column], errors='raise')
            numeric_columns.append(column)
        except (ValueError, TypeError):
            non_numeric_columns.append(column)

    df_final = df[numeric_columns]
    cols_removed = df.shape[1] - df_final.shape[1]

    if fill_na_with_zero:
        df_final = df_final.fillna(0)

    # Формируем детали (возвращаем строку с описанием, как в оригинале)
    details = f"""ПРЕДОБРАБОТКА ДАННЫХ:

Исходные размеры данных: {original_shape}"""

    if drop_first_column and original_shape[1] > 0:
        details += f"\nУдален первый столбец: {original_columns[0] if original_columns else ''}"

    details += f"""
Обработка пропусков: {'Замена на 0' if fill_na_with_zero else 'Удаление строк'}
Удалено строк: {rows_removed}
Удалено нечисловых столбцов: {cols_removed}
Финальные размеры данных: {df_final.shape}
Сохранилось {100 * df_final.shape[0] / original_shape[0]:.1f}% строк
Сохранилось {100 * df_final.shape[1] / (original_shape[1] - (1 if drop_first_column else 0)):.1f}% столбцов

ПЕРЕИМЕНОВАНИЕ СТОЛБЦОВ:"""

    for i, (old, new) in enumerate(zip(original_columns, final_columns)):
        if str(old) != new:
            details += f"\n  '{old}' -> '{new}'"

    if encoded_summary:
        details += f"\n\nКАТЕГОРИАЛЬНОЕ КОДИРОВАНИЕ (One-Hot Encoding, макс. {max_categories}):"
        for orig_col, uv, new_cols in encoded_summary:
            details += f"\n  '{orig_col}' ({uv} уникальных) -> {len(new_cols)} бинарных столбцов"
            if len(new_cols) > 0:
                sample = new_cols[:3]
                details += f" (пример: {', '.join(sample)}{'...' if len(new_cols) > 3 else ''})"

    if non_numeric_columns:
        details += f"\n\nУдаленные нечисловые столбцы: {non_numeric_columns}"

    details += "\n\nТИПЫ ДАННЫХ ПОСЛЕ ПРЕОБРАЗОВАНИЯ:"
    for column in df_final.columns:
        details += f"\n  {column}: {df_final[column].dtype}"

    print(f"  Предобработка завершена: {df_final.shape[0]} строк, {df_final.shape[1]} столбцов")

    return df_final, details