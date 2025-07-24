import logging
import json
import base64
from pathlib import Path
from typing import Optional, Dict, Any, List
import uuid

from fastapi import APIRouter, Request, HTTPException, status, UploadFile, Form
from fastapi.responses import JSONResponse

from api.models import APIResponse, DocumentMetadata, ProcessedDocument
from knowledge_graph.models import GraphBuild
from setting.db import SessionLocal, db_manager
from tools.api_integration import PipelineAPIIntegration

# Functions imported from api.knowledge for reuse
from api.knowledge import (
    _validate_file,
    _save_uploaded_file_with_metadata,
    _create_processing_task,
    _get_file_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingest"])


# --- Tool-based Processing Functions ---

api_integration = PipelineAPIIntegration()


async def _process_files_with_pipeline(
    files: List[UploadFile], metadata: Dict[str, Any], process_strategy: Dict[str, Any]) -> JSONResponse:
    """Process uploaded files using the new tool-based pipeline with in-memory processing."""
    
    topic_name = metadata.get("topic_name")
    link = metadata.get("link")
    database_uri = metadata.get("database_uri")
    custom_metadata = {
        k: v
        for k, v in metadata.items()
        if k not in ["topic_name", "link", "database_uri"]
    }

    if not topic_name or not link:
        raise HTTPException(
            status_code=400,
            detail="`topic_name` and `link` are required in metadata for target_type 'knowledge_graph'.",
        )

    try:
        # Validate all files
        for file in files:
            _validate_file(file)
        
        file_count = len(files)
        
        # Prepare request data in SmartSave API format
        request_data = {
            "target_type": "knowledge_graph",
            "metadata": {
                "topic_name": topic_name,
                "link": link,
                "database_uri": database_uri,
                "file_count": file_count,
                "is_new_topic": metadata.get("is_new_topic", file_count > 1),
                **custom_metadata
            },
            "process_strategy": process_strategy or {}
        }

        # Prepare file information for DocumentETLTool using SmartSave format
        file_contexts = []
        for file in files:
            file_content = await file.read()
            file_contexts.append({
                "file_content": base64.b64encode(file_content).decode('utf-8'),
                "file_name": file.filename or f"file_{len(file_contexts) + 1}",
                "file_type": file.content_type or "application/octet-stream",
                "topic_name": topic_name,
                "link": f"{link}/file_{len(file_contexts) + 1}",
                "metadata": custom_metadata
            })

        # Execute pipeline using orchestrator
        result = api_integration.process_request(request_data, file_contexts)

        # Create response for multiple files
        processed_docs = []
        for i, file in enumerate(files):
            processed_docs.append(ProcessedDocument(
                id=f"{result.execution_id}_{i}" if result.execution_id else str(uuid.uuid4()),
                name=file.filename or f"file_{i + 1}",
                file_path=f"inline://{file.filename or f'uploaded_file_{i + 1}'}",
                doc_link=f"{link}/file_{i + 1}",
                file_type=_get_file_type(Path(file.filename or f"file_{i + 1}")),
                status="processing" if result.success else "failed",
            ).model_dump())

        response = APIResponse(
            status="success" if result.success else "error",
            message=result.message or f"Processing {file_count} files completed",
            data=processed_docs,
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK if result.success else status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump()
        )

    except Exception as e:
        logger.error(f"Failed to process files with pipeline: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "error",
                "message": f"Failed to process files: {str(e)}",
                "data": None
            }
        )




async def _process_file_for_knowledge_graph(
    file: UploadFile, metadata: Dict[str, Any], process_strategy: Dict[str, Any]
) -> JSONResponse:
    """Processes an uploaded file to build a knowledge graph."""
    _validate_file(file)

    topic_name = metadata.get("topic_name")
    link = metadata.get("link")
    database_uri = metadata.get("database_uri")
    custom_metadata = {
        k: v
        for k, v in metadata.items()
        if k not in ["topic_name", "link", "database_uri"]
    }

    if not topic_name or not link:
        raise HTTPException(
            status_code=400,
            detail="`topic_name` and `link` are required in metadata for target_type 'knowledge_graph'.",
        )

    file_metadata = DocumentMetadata(
        doc_link=link,
        topic_name=topic_name,
        database_uri=database_uri,
        custom_metadata=custom_metadata,
    )

    storage_directory, build_id = _save_uploaded_file_with_metadata(
        file, file_metadata
    )

    is_existing = False
    external_db_uri = (
        "" if db_manager.is_local_mode(database_uri) else database_uri or ""
    )
    with SessionLocal() as db:
        build_status = (
            db.query(GraphBuild)
            .filter(
                GraphBuild.build_id == build_id,
                GraphBuild.topic_name == topic_name,
                GraphBuild.external_database_uri == external_db_uri,
            )
            .first()
        )
        if build_status:
            is_existing = True

    if is_existing:
        status_msg = "already_exists"
    else:
        _create_processing_task(storage_directory, file_metadata, build_id)
        status_msg = "uploaded"

    processed_doc = ProcessedDocument(
        id=build_id,
        name=file.filename or "unknown",
        file_path=str(storage_directory),
        doc_link=link,
        file_type=_get_file_type(Path(file.filename or "unknown")),
        status=status_msg,
    )

    response = APIResponse(
        status="success",
        message=f"Successfully processed file for knowledge graph. Status: {status_msg}",
        data=processed_doc.model_dump(),
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=response.model_dump())


async def _process_json_for_personal_memory(
    input_data: Any, metadata: Dict[str, Any], process_strategy: Dict[str, Any]
) -> JSONResponse:
    """Processes JSON input (chat history) to build personal memory."""
    user_id = metadata.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="`user_id` is required in metadata for target_type 'personal_memory'.",
        )

    if not isinstance(input_data, list):
        raise HTTPException(
            status_code=400,
            detail="Input data for personal memory must be a list of chat messages.",
        )

    # Use tool-based pipeline for memory processing instead of standalone system
    from tools.api_integration import PipelineAPIIntegration
    api_integration = PipelineAPIIntegration()
    
    # Prepare request for memory pipeline - unified flow
    request_data = {
        "target_type": "personal_memory",
        "metadata": {
            "user_id": user_id
        },
        "input": input_data
        # Let orchestrator select appropriate pipeline automatically
    }
    
    result = api_integration.process_request(request_data, [])

    response = APIResponse(
        status="success",
        message=f"Successfully processed {len(input_data)} messages for personal memory",
        data=result,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=response.dict())


async def _process_json_for_knowledge_graph(
    input_data: Any, metadata: Dict[str, Any], process_strategy: Dict[str, Any]) -> JSONResponse:
    """Process JSON input for knowledge graph using tool-based pipeline."""
    topic_name = metadata.get("topic_name")
    if not topic_name:
        raise HTTPException(
            status_code=400,
            detail="`topic_name` is required in metadata for target_type 'knowledge_graph'.",
        )

    # Handle different input formats
    if isinstance(input_data, str):
        # Text content
        content = input_data
    elif isinstance(input_data, dict):
        # JSON content
        content = json.dumps(input_data)
    else:
        content = str(input_data)

    # Prepare request data in SmartSave API format
    request_data = {
        "target_type": "knowledge_graph",
        "metadata": metadata,
        "process_strategy": process_strategy or {}
    }

    # Prepare content for processing using SmartSave format
    context = {
        "content": content,
        "file_name": "input.json",
        "file_type": "text/plain",
        "topic_name": metadata.get("topic_name"),
        "link": metadata.get("link", "inline_input"),
        "metadata": {},
        **request_data
    }

    # Execute pipeline using orchestrator
    result = api_integration.process_request(request_data, [context])

    # Create response
    processed_doc = ProcessedDocument(
        id=result.execution_id or str(uuid.uuid4()),
        name="input.json",
        file_path="inline://input.json",
        doc_link=metadata.get("link", "inline_input"),
        file_type="json",
        status="processing" if result.success else "failed",
    )

    response = APIResponse(
        status="success" if result.success else "error",
        message=result.message or "Processing completed",
        data=processed_doc.model_dump(),
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK if result.success else status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump()
    )


# --- Request Handlers ---


async def _handle_form_data(
    files: List[UploadFile],
    metadata_str: str,
    target_type: str,
    process_strategy: Optional[dict] = None,
) -> JSONResponse:
    """Handles multipart/form-data for file uploads (supports multiple files)."""
    try:
        metadata = json.loads(metadata_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in metadata.",
        )

    # Dispatch based on target_type for form-data
    if target_type == "knowledge_graph":
        # Use new tool-based pipeline system with multiple files
        return await _process_files_with_pipeline(files, metadata, process_strategy or {})
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target_type '{target_type}' for file uploads.",
        )


async def _handle_json_data(request: Request) -> JSONResponse:
    """Handles application/json for raw data, like chat history."""
    try:
        data = await request.json()
        input_data = data.get("input")
        metadata: Dict[str, Any] = data.get("metadata", {})
        target_type = data.get("target_type")
        process_strategy: Dict[str, Any] = data.get("process_strategy", {})

        if not isinstance(process_strategy, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="process_strategy must be a JSON object.",
            )

        if not input_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Input data is missing."
            )
        if not target_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="`target_type` is a required field for JSON input.",
            )

        # Dispatch based on target_type for JSON
        if target_type == "personal_memory":
            return await _process_json_for_personal_memory(
                input_data, metadata, process_strategy
            )
        elif target_type == "knowledge_graph":
            return await _process_json_for_knowledge_graph(
                input_data, metadata, process_strategy
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported target_type '{target_type}' for JSON input.",
            )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        )
    except Exception as e:
        logger.error(f"Failed to process json data: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process JSON input: {str(e)}",
        )


@router.post("/save", response_model=APIResponse, status_code=status.HTTP_200_OK)
async def save_data(
    request: Request,
    files: Optional[List[UploadFile]] = Form(None),
    metadata: Optional[str] = Form(None),
    target_type: Optional[str] = Form(None),
    process_strategy: Optional[str] = Form(None),
) -> JSONResponse:
    """
    Unified endpoint to save data from file uploads or raw JSON input.

    This endpoint supports both `multipart/form-data` for files and `application/json` for structured data.
    The processing behavior is determined by `target_type`.

    **For File Uploads (`multipart/form-data`):**
    - `files[]`: One or more files to be uploaded.
    - `metadata`: A JSON string with fields like `topic_name`, `link`, etc.
    - `target_type`: The desired output (e.g., "knowledge_graph").
    - `process_strategy` (optional): A JSON string representing a dictionary for processing options.

    **For JSON Input (`application/json`):**
    - `input`: The raw data (e.g., list of chat messages).
    - `metadata`: A JSON object with relevant context (e.g., `user_id`).
    - `target_type`: The desired output (e.g., "personal_memory").
    - `input_type`: A hint about the input format (e.g., "chat_history").
    - `process_strategy` (optional): A JSON object for processing options.
    """
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        if not files or not metadata or not target_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For multipart/form-data, 'files[]', 'metadata', and 'target_type' are required.",
            )
        # Parse process_strategy from string to dict if provided
        parsed_process_strategy = None
        if process_strategy:
            try:
                parsed_process_strategy = json.loads(process_strategy)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON in process_strategy.",
                )
        return await _handle_form_data(files, metadata, target_type, parsed_process_strategy)
    elif "application/json" in content_type:
        return await _handle_json_data(request)
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type. Use application/json or multipart/form-data.",
        )
