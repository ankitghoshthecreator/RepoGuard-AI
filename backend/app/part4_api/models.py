from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class IngestRequest(BaseModel):
    repo_url: str
    branch: Optional[str] = "main"

class ReviewRequest(BaseModel):
    repo_id: str
    pr_id: Optional[str] = None
    code_diff: Optional[str] = None

class AnalysisResponse(BaseModel):
    status: str
    summary: str
    findings: Dict[str, Any]
