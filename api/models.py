"""
API data models for request/response schemas.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata for uploaded documents."""

    doc_link: str
    topic_name: str


class ProcessedDocument(BaseModel):
    """Information about a processed document."""

    id: str
    name: str
    file_path: str
    doc_link: Optional[str] = None
    file_type: str
    status: str = "processed"


class DocumentInfo(BaseModel):
    """Document information."""

    id: str
    name: str
    doc_link: Optional[str] = None
    file_type: str
    content_preview: str
    created_at: str
    updated_at: str
    build_statuses: List[Dict[str, Any]] = []
    graph_elements: Dict[str, List[Dict[str, str]]] = {
        "entities": [],
        "relationships": [],
    }


class APIResponse(BaseModel):
    """Standard API response."""

    status: str = "success"
    data: Any
    message: Optional[str] = None
