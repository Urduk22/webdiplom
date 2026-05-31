import pandas as pd
import numpy as np

def apply_correlation_threshold(df, threshold):
    print(f"  Начинаем вычисление корреляции...")
    print(f"  Вычисляем корреляцию для {len(df):,} строк...")
    correlation_matrix = df.corr()
    correlation_matrix = correlation_matrix.fillna(0)
    print(f"  Заменено NaN значений: {(correlation_matrix.isnull().sum().sum())}")

    correlation_filtered = np.abs(correlation_matrix.copy())
    correlation_filtered[correlation_filtered < threshold] = 0

    details = f"МАТРИЦА КОРРЕЛЯЦИИ (порог: {threshold}):\n"
    details += str(correlation_filtered)

    print(f"  Матрица корреляции готова: {correlation_filtered.shape}")
    return correlation_filtered, details