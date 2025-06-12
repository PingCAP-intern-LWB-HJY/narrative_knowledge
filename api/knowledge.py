"""
Knowledge document upload API endpoints.
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse

from api.models import DocumentMetadata, ProcessedDocument, DocumentInfo, APIResponse
from knowledge_graph.knowledge import KnowledgeBuilder
from knowledge_graph.models import (
    SourceData,
    GraphBuildStatus,
    SourceGraphMapping,
    Entity,
    Relationship,
)
from typing import List
from setting.db import SessionLocal
from sqlalchemy import or_, and_, func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])

# Initialize knowledge builder
kb_builder = KnowledgeBuilder()

# Configuration
UPLOAD_DIR = Path("uploads")
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".sql"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _ensure_upload_dir() -> None:
    """Ensure upload directory exists."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _validate_file(file: UploadFile) -> None:
    """
    Validate uploaded file including filename, type, and size.

    Args:
        file: The uploaded file to validate

    Raises:
        HTTPException: If file validation fails
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must have a filename"
        )

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file_ext} not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check file size
    file.file.seek(0, 2)  # Seek to end of file
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {MAX_FILE_SIZE // (1024*1024)}MB limit",
        )


def _save_uploaded_file(file: UploadFile, topic_name: str) -> Path:
    """
    Save uploaded file to disk in its own directory.
    Structure: UPLOAD_DIR/filename/filename

    Args:
        file: The uploaded file to save

    Returns:
        Path to the saved file

    Raises:
        HTTPException: If file saving fails
    """
    try:
        _ensure_upload_dir()

        # Create directory structure: UPLOAD_DIR/filename
        filename = file.filename
        file_dir = UPLOAD_DIR / topic_name / filename
        if file_dir.exists():
            return file_dir / filename

        # Create the file directory
        file_dir.mkdir(parents=True, exist_ok=True)

        # Save file inside its directory
        file_path = file_dir / filename

        # Write file content
        with open(file_path, "wb") as buffer:
            content = file.file.read()
            buffer.write(content)

        logger.info(f"File saved successfully: {file_path}")
        return file_path

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save file {file.filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}",
        )


def _process_document(file_path: Path, metadata: DocumentMetadata) -> ProcessedDocument:
    """
    Process uploaded document using knowledge builder and create build status record.

    Args:
        file_path: Path to the uploaded file
        metadata: Document metadata including doc_link and topic_name

    Returns:
        ProcessedDocument with extraction results

    Raises:
        Exception: If document processing fails
    """
    try:
        # Prepare attributes for knowledge extraction
        attributes = {"doc_link": metadata.doc_link, "topic_name": metadata.topic_name}

        # Extract knowledge using existing knowledge builder
        result = kb_builder.extract_knowledge(str(file_path), attributes)

        if result["status"] != "success":
            raise Exception(
                f"Knowledge extraction failed: {result.get('error', 'Unknown error')}"
            )

        # Create GraphBuildStatus record
        kb_builder.create_build_status_record(result["source_id"], metadata.topic_name)

        return ProcessedDocument(
            id=result["source_id"],
            name=result["source_name"],
            file_path=str(file_path),
            doc_link=metadata.doc_link,
            file_type=_get_file_type(file_path),
            status="processed",
        )

    except Exception as e:
        logger.error(f"Failed to process document {file_path}: {e}")
        raise


def _get_file_type(file_path: Path) -> str:
    """
    Determine file type from extension.

    Args:
        file_path: Path to the file

    Returns:
        File type string
    """
    extension = file_path.suffix.lower()
    type_mapping = {".pdf": "pdf", ".md": "markdown", ".txt": "document", ".sql": "sql"}
    return type_mapping.get(extension, "unknown")


@router.post("/upload", response_model=APIResponse)
async def upload_documents(
    files: List[UploadFile] = File(..., description="Files to upload"),
    doc_link: str = Form(..., description="Link to the original document"),
    topic_name: str = Form(..., description="Topic name for knowledge graph building"),
) -> JSONResponse:
    """
    Upload and process documents for knowledge graph building.

    This endpoint accepts one or more files and processes them through the knowledge
    extraction pipeline. Each file is validated, saved, and processed to extract
    knowledge content. A build status record is created for each document.

    Args:
        files: List of files to upload (supports pdf, md, txt, sql)
        metadata: Required metadata including doc_link and topic_name

    Returns:
        JSON response with upload results including processed document information

    Raises:
        HTTPException: If validation fails or processing errors occur
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided"
        )

    processed_documents: List[ProcessedDocument] = []
    failed_uploads = []

    # Create metadata object from form fields
    metadata = DocumentMetadata(doc_link=doc_link, topic_name=topic_name)

    for file in files:
        try:
            # Validate file
            _validate_file(file)

            # Save file
            file_path = _save_uploaded_file(file, topic_name)

            # Process document
            processed_doc = _process_document(file_path, metadata)
            processed_documents.append(processed_doc)

            logger.info(f"Successfully processed document: {file.filename}")

        except HTTPException:
            # Re-raise HTTP exceptions (validation errors)
            raise
        except Exception as e:
            # Handle processing errors - continue with other files
            error_detail = {"file": file.filename or "unknown", "reason": str(e)}
            failed_uploads.append(error_detail)
            logger.error(f"Failed to process file {file.filename}: {e}")

    # If all files failed, return error
    if not processed_documents and failed_uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UPLOAD_FAILED",
                "message": "All files failed to process",
                "details": failed_uploads,
            },
        )

    # Prepare response
    response_data = {
        "uploaded_count": len(processed_documents),
        "documents": [doc.dict() for doc in processed_documents],
        "failed": failed_uploads,
    }

    response = APIResponse(
        status="success", message="Documents uploaded successfully", data=response_data
    )

    return JSONResponse(status_code=status.HTTP_200_OK, content=response.dict())


@router.get("/", response_model=APIResponse)
async def list_documents(
    topic_name: str = None,
    name: str = None,
    doc_link: str = None,
    limit: int = 20,
    offset: int = 0,
) -> JSONResponse:
    """
    List documents with optional filtering.

    Args:
        topic_name: Filter by topic name (exact match)
        name: Filter by document name (partial match)
        doc_link: Filter by original document link (exact match)
        limit: Maximum number of results (default 20, max 100)
        offset: Number of results to skip (default 0)

    Returns:
        JSON response with list of documents and pagination info
    """
    try:
        if limit > 100:
            limit = 100
        if limit < 1:
            limit = 20

        with SessionLocal() as db:
            query = db.query(SourceData)

            # Apply filters
            if topic_name:
                query = query.join(GraphBuildStatus).filter(
                    GraphBuildStatus.topic_name == topic_name
                )
            if name:
                query = query.filter(SourceData.name.ilike(f"%{name}%"))
            if doc_link:
                query = query.filter(SourceData.link == doc_link)

            total_count = query.count()
            documents = query.offset(offset).limit(limit).all()

            # Build response with optimized batch queries
            document_infos = _build_documents_info_batch(db, documents)

            response_data = {
                "documents": [doc.dict() for doc in document_infos],
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count,
            }

            response = APIResponse(data=response_data)

            return JSONResponse(status_code=status.HTTP_200_OK, content=response.dict())

    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve documents",
        )


@router.get("/{document_id}", response_model=APIResponse)
async def get_document_detail(document_id: str) -> JSONResponse:
    """
    Get information about a specific document.

    Args:
        document_id: The document ID to retrieve

    Returns:
        JSON response with document information
    """
    try:
        with SessionLocal() as db:
            document = db.query(SourceData).filter(SourceData.id == document_id).first()

            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
                )

            # Use batch function for consistency and performance
            doc_infos = _build_documents_info_batch(db, [document])
            doc_info = doc_infos[0] if doc_infos else None

            response = APIResponse(data=doc_info.dict())

            return JSONResponse(status_code=status.HTTP_200_OK, content=response.dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve document",
        )


def _build_documents_info_batch(db, documents: List[SourceData]) -> List[DocumentInfo]:
    """
    Build DocumentInfo list with optimized batch queries.

    Args:
        db: Database session
        documents: List of SourceData instances

    Returns:
        List of DocumentInfo with populated data
    """
    if not documents:
        return []

    document_ids = [doc.id for doc in documents]

    # Batch query build statuses
    build_statuses = (
        db.query(GraphBuildStatus)
        .filter(GraphBuildStatus.source_id.in_(document_ids))
        .all()
    )

    # Group build statuses by source_id
    build_statuses_map = {}
    for status in build_statuses:
        if status.source_id not in build_statuses_map:
            build_statuses_map[status.source_id] = []
        build_statuses_map[status.source_id].append(
            {
                "topic_name": status.topic_name,
                "status": status.status,
                "created_at": status.created_at.isoformat(),
                "updated_at": status.updated_at.isoformat(),
                "scheduled_at": status.scheduled_at.isoformat(),
                "error_message": status.error_message,
            }
        )

    # Batch query graph mappings
    graph_mappings = (
        db.query(SourceGraphMapping)
        .filter(SourceGraphMapping.source_id.in_(document_ids))
        .all()
    )

    # Get all entity and relationship IDs
    entity_ids = [
        m.graph_element_id for m in graph_mappings if m.graph_element_type == "entity"
    ]
    relationship_ids = [
        m.graph_element_id
        for m in graph_mappings
        if m.graph_element_type == "relationship"
    ]

    # Batch query entities and relationships
    entities_map = {}
    if entity_ids:
        entities = (
            db.query(Entity.id, Entity.name, Entity.description)
            .filter(Entity.id.in_(entity_ids))
            .all()
        )
        entities_map = {
            e.id: {"id": e.id, "name": e.name, "description": e.description or ""}
            for e in entities
        }

    relationships_map = {}
    if relationship_ids:
        from sqlalchemy.orm import aliased

        SourceEntity = aliased(Entity)
        TargetEntity = aliased(Entity)

        relationships = (
            db.query(
                Relationship.id,
                SourceEntity.name.label("source_entity_name"),
                TargetEntity.name.label("target_entity_name"),
                Relationship.relationship_desc,
            )
            .join(SourceEntity, Relationship.source_entity_id == SourceEntity.id)
            .join(TargetEntity, Relationship.target_entity_id == TargetEntity.id)
            .filter(Relationship.id.in_(relationship_ids))
            .all()
        )
        relationships_map = {
            r.id: {
                "id": r.id,
                "source_entity_name": r.source_entity_name,
                "target_entity_name": r.target_entity_name,
                "relationship_desc": r.relationship_desc or "",
            }
            for r in relationships
        }

    # Group graph elements by source_id
    graph_elements_map = {}
    for mapping in graph_mappings:
        if mapping.source_id not in graph_elements_map:
            graph_elements_map[mapping.source_id] = {
                "entities": [],
                "relationships": [],
            }

        if (
            mapping.graph_element_type == "entity"
            and mapping.graph_element_id in entities_map
        ):
            entity = entities_map[mapping.graph_element_id]
            graph_elements_map[mapping.source_id]["entities"].append(
                {
                    "id": entity["id"],
                    "name": entity["name"],
                    "description": entity["description"],
                }
            )
        elif (
            mapping.graph_element_type == "relationship"
            and mapping.graph_element_id in relationships_map
        ):
            relationship = relationships_map[mapping.graph_element_id]
            graph_elements_map[mapping.source_id]["relationships"].append(
                {
                    "id": relationship["id"],
                    "name": f"{relationship['source_entity_name']} -> {relationship['target_entity_name']}",
                    "description": relationship["relationship_desc"],
                }
            )

    # Build document info list
    document_infos = []
    for doc in documents:
        # Get build statuses for this document
        doc_build_statuses = build_statuses_map.get(doc.id, [])

        # Get graph elements for this document
        doc_graph_elements = graph_elements_map.get(
            doc.id, {"entities": [], "relationships": []}
        )

        # Content preview
        content_preview = ""
        if doc.content:
            content_preview = doc.content[:500]
            if len(doc.content) > 500:
                content_preview += "..."

        document_info = DocumentInfo(
            id=doc.id,
            name=doc.name,
            doc_link=doc.link,
            file_type=doc.source_type,
            content_preview=content_preview,
            created_at=doc.created_at.isoformat(),
            updated_at=doc.updated_at.isoformat(),
            build_statuses=doc_build_statuses,
            graph_elements=doc_graph_elements,
        )
        document_infos.append(document_info)

    return document_infos
