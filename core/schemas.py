from pydantic import BaseModel
from typing import List, Optional

class AnalysisParams(BaseModel):
    """Параметры анализа, передаваемые через API"""
    drop_first: bool = False
    fill_na_zero: bool = True
    encode_cat: bool = False
    max_cat: int = 10
    threshold: float = 0.3
    n_launches: int = 10
    n_solutions: int = 100
    cap: int = 1000
    frac: float = 0.35
    q: float = 1.0
    target_column: str = ""   # имя целевого столбца (необязательно)

class AnalysisResponse(BaseModel):
    """Ответ API с результатами анализа"""
    selected_columns: List[str]
    w_max: float
    correlation_file: str
    algorithm_file: str
    num_rows: int
    num_cols: int
    process_details: str
    correlation_details: str
    algorithm_details: str
    target_column: str = ""   # возвращаем, какой целевой столбец был использован

class FileUploadResponse(BaseModel):
    """Ответ после загрузки файла (для последующего анализа по ID)"""
    file_id: str
    filename: str