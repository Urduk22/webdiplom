import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import engine
from models import Base
from backend.controller import auth, survey, analysis
from backend.service.analysis_service import RESULTS_DIR


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Survey Data Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(survey.router)
app.include_router(analysis.router)

BUILD_DIR = "frontend/build"
if os.path.exists(BUILD_DIR) and os.path.isdir(BUILD_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(BUILD_DIR, "static")), name="static")

    favicon_path = os.path.join(BUILD_DIR, "favicon.ico")
    if os.path.exists(favicon_path):
        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            return FileResponse(favicon_path)


    @app.get("/api/download/{filename}")
    async def download_file(filename: str):
        file_path = os.path.join(RESULTS_DIR, filename)
        if os.path.exists(file_path):
            return FileResponse(file_path, media_type='application/octet-stream', filename=filename)
        raise HTTPException(status_code=404, detail="File not found")
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        if full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = os.path.join(BUILD_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(BUILD_DIR, "index.html"))
else:
    print("WARNING: frontend/build directory not found. Frontend will not be served.")

@app.get("/api/health")
async def health():
    return {"status": "ok"}
