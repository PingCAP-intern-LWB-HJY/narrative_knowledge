import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Awaitable

from fastapi import APIRouter, Request, HTTPException, status, UploadFile, Form
from fastapi.responses import JSONResponse

from api.models import APIResponse, DocumentMetadata, ProcessedDocument
from api.memory import _get_memory_system
from knowledge_graph.models import GraphBuild
from setting.db import SessionLocal, db_manager

# Functions imported from api.knowledge for reuse
from api.knowledge import (
    _validate_file,
    _save_uploaded_file_with_metadata,
    _create_processing_task,
    _get_file_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["ingest"])


# --- Processing Functions ---


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
        data=processed_doc.dict(),
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=response.dict())


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

    memory_system = _get_memory_system()
    result = memory_system.process_chat_batch(chat_messages=input_data, user_id=user_id)

    response = APIResponse(
        status="success",
        message=f"Successfully processed {len(input_data)} messages for personal memory",
        data=result,
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=response.dict())


# --- Request Handlers ---


async def _handle_form_data(
    file: UploadFile,
    metadata_str: str,
    target_type: str,
    process_strategy: Optional[dict] = None,
) -> JSONResponse:
    """Handles multipart/form-data for file uploads."""
    try:
        metadata = json.loads(metadata_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in metadata.",
        )

    # Dispatch based on target_type for form-data
    if target_type == "knowledge_graph":
        return await _process_file_for_knowledge_graph(file, metadata, process_strategy or {})
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
    file: Optional[UploadFile] = Form(None),
    metadata: Optional[str] = Form(None),
    target_type: Optional[str] = Form(None),
    process_strategy: Optional[str] = Form(None),
) -> JSONResponse:
    """
    Unified endpoint to save data from file uploads or raw JSON input.

    This endpoint supports both `multipart/form-data` for files and `application/json` for structured data.
    The processing behavior is determined by `target_type`.

    **For File Uploads (`multipart/form-data`):**
    - `file`: The file to be uploaded.
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
        if not file or not metadata or not target_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For multipart/form-data, 'file', 'metadata', and 'target_type' are required.",
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
        return await _handle_form_data(file, metadata, target_type, parsed_process_strategy)
    elif "application/json" in content_type:
        return await _handle_json_data(request)
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type. Use application/json or multipart/form-data.",
        )

from tools.route_wrapper import ToolsRouteWrapper

# 在模块级别创建包装器实例
tools_wrapper = ToolsRouteWrapper()

@router.post("/save_pipeline", response_model=APIResponse, status_code=status.HTTP_200_OK)
async def save_data_pipeline(
    request: Request,
    file: Optional[UploadFile] = Form(None),
    metadata: Optional[str] = Form(None),
    target_type: Optional[str] = Form(None),
    process_strategy: Optional[str] = Form(None),
) -> JSONResponse:
    """
    Enhanced save endpoint using tools pipeline system.
    """
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        # 文件上传处理
        if not file or not metadata or not target_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For multipart/form-data, 'file', 'metadata', and 'target_type' are required.",
            )
        
        # 使用 tools 包装器处理
        result = tools_wrapper.process_upload_request(
            files=file,
            metadata=metadata,
            process_strategy=process_strategy,
            target_type=target_type
        )
        logger.info(f"Processed upload request: {result.to_dict()}")
        # 转换为 API 响应格式
        if result.success:
            return JSONResponse(
                status_code=200,
                content=result.to_dict()
            )
        else:
            return JSONResponse(
                status_code=500,
                content=result.to_dict()
            )

    elif "application/json" in content_type:
        # JSON 数据处理
        body = await request.json()
        
        result = tools_wrapper.process_json_request(
            input_data=body.get("input"),
            metadata=body.get("metadata", {}),
            process_strategy=body.get("process_strategy"),
            target_type=body.get("target_type", "personal_memory")
        )
        
        # Convert ToolResult to dict for JSON serialization
        result_dict = result.to_dict()
        
        if result.success:
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "Processing completed successfully", 
                    "data": result_dict["data"],
                    "execution_id": result_dict["execution_id"]
                }
            )
        else:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": result_dict["error_message"],
                    "execution_id": result_dict["execution_id"]
                }
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type. Use application/json or multipart/form-data.",
        )