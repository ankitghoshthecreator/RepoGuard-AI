from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.part4_api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise AI Platform for Automated Code Review, Security Analysis, Architecture Inspection, and Pull Request Intelligence."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/")
def root():
    return {
        "message": "Welcome to RepoGuard AI Platform",
        "docs_url": "/docs",
        "parts": {
            "part1": "Code Ingestion, AST & Static Analysis Engine",
            "part2": "Knowledge Graph & Hybrid RAG Engine",
            "part3": "Multi-Agent AI Reasoning & PR Intelligence",
            "part4": "FastAPI Backend & Interactive UI Dashboard"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
