from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum

class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

class UploadResponse(BaseModel):
    """Réponse endpoint /upload"""
    document_id: str
    status: ProcessingStatus
    rejected_at_gate: Optional[int] = None
    rejection_reason: Optional[str] = None
    file_type: Optional[str] = None
    quality_score: Optional[Dict[str, Any]] = None
    message: str
    suggestions: List[str] = []
    metadata: Dict[str, Any] = {}