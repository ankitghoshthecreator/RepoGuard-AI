from fastapi import APIRouter, Depends
from .models import IngestRequest, ReviewRequest, AnalysisResponse
from .webhooks import webhook_router
from backend.app.part1_parser.ingestion import RepoIngestor
from backend.app.part1_parser.static_scanner import StaticSecurityScanner
from backend.app.part2_knowledge.graph_builder import KnowledgeGraphBuilder
from backend.app.part3_agents.orchestrator import LangGraphOrchestrator

api_router = APIRouter()
api_router.include_router(webhook_router, prefix="/webhooks", tags=["webhooks"])

@api_router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "RepoGuard AI Platform",
        "modules": [
            "Part 1: Ingestion & AST Parser",
            "Part 2: Knowledge Graph & Hybrid RAG",
            "Part 3: Multi-Agent Reasoning Core",
            "Part 4: FastAPI Server & Webhooks"
        ]
    }

@api_router.post("/ingest", response_model=AnalysisResponse)
def ingest_repository(req: IngestRequest):
    ingestor = RepoIngestor(req.repo_url)
    result = ingestor.clone_or_load()
    return AnalysisResponse(
        status="success",
        summary=f"Ingested repository successfully with {result['file_count']} files.",
        findings=result
    )

@api_router.post("/review", response_model=AnalysisResponse)
def review_code(req: ReviewRequest):
    orchestrator = LangGraphOrchestrator()
    review_res = orchestrator.run_pr_review_workflow(req.code_diff or "", {})
    return AnalysisResponse(
        status="success",
        summary=review_res["pr_summary"],
        findings=review_res
    )
