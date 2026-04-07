from pydantic import BaseModel
from typing import List, Optional

class AnalysisParams(BaseModel):
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
    target_column: str = ""
    method: str = "graph"          # 'graph', 'correlation', 'anova', 'pca'
    top_k: int = 10

class AnalysisResponse(BaseModel):
    selected_columns: List[str]
    w_max: float
    correlation_file: str
    algorithm_file: str
    num_rows: int
    num_cols: int
    process_details: str
    correlation_details: str
    algorithm_details: str
    target_column: str = ""
    method: str = "graph"
    comparison_results: Optional[dict] = None

class FileUploadResponse(BaseModel):
    file_id: str
    filename: str