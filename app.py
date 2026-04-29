import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
from models import Base
from backend.controller import auth, survey, analysis

# Создание таблиц БД (добавьте эту строку!)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Survey Data Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(survey.router)
app.include_router(analysis.router)

@app.get("/")
async def root():
    return {"message": "Survey Data Analyzer API"}