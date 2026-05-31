from pydantic import BaseModel
from typing import List, Optional

class QuestionCreate(BaseModel):
    text: str
    question_type: str
    order: int
    options: List[str] = []
    scale_min: int = 1
    scale_max: int = 10

class SurveyCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    questions: List[QuestionCreate]

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
    method: str = "graph"
    top_k: int = 10