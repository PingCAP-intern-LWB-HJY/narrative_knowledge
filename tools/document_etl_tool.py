"""
DocumentETLTool: Processes a single raw document file.

- Purpose: To process a single raw document file
- Input: Raw file (e.g., PDF, TXT), Topic ID
- Output: Structured SourceData (text, initial entities, etc.)
- Maps to: KnowledgeBuilder.build_from_file logic
"""

import hashlib
import os
import base64
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import io

from tools.base import BaseTool, ToolResult
from etl.extract import extract_source_data, extract_data_from_text_file
from knowledge_graph.models import RawDataSource, SourceData, ContentStore
from setting.db import SessionLocal


class DocumentETLTool(BaseTool):
    """
    Processes a single raw document file into structured SourceData.
    
    This tool takes a raw file and topic information, extracts content,
    and creates structured SourceData for further processing.
    
    Input Schema:
        file_path (str): Path to the document file
        topic_name (str): Topic name for grouping documents
        metadata (dict, optional): Custom metadata to attach
        force_reprocess (bool, optional): Force reprocessing even if already processed
        link (str, optional): Document URL/link
        original_filename (str, optional): Original filename if different from file_path
    
    Output Schema:
        source_data_id (str): ID of created SourceData record
        content_hash (str): SHA-256 hash of extracted content
        content_size (int): Size of extracted content in bytes
        source_type (str): Detected content type (pdf, txt, etc.)
        reused_existing (bool): Whether existing SourceData was reused
        status (str): Processing status (created, already_processed, etc.)
    """
    
    def __init__(self, session_factory=None):
        super().__init__(session_factory=session_factory)
        self.session_factory = session_factory or SessionLocal
    
    @property
    def tool_name(self) -> str:
        return "DocumentETLTool"
        
    @property
    def tool_key(self) -> str:
        return "etl"
    
    @property
    def tool_description(self) -> str:
        return "Processes a single raw document file into structured SourceData"
    
    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the document file (legacy, optional if file_content provided)"
                },
                "file_content": {
                    "type": "string",
                    "description": "Base64 encoded file content for in-memory processing"
                },
                "file_name": {
                    "type": "string",
                    "description": "Original filename for content-based processing"
                },
                "file_type": {
                    "type": "string",
                    "description": "MIME type of the file (e.g., application/pdf, text/plain)"
                },
                "topic_name": {
                    "type": "string",
                    "description": "Topic name for grouping documents"
                },
                "metadata": {
                    "type": "object",
                    "description": "Custom metadata to attach to the document",
                    "default": {}
                },
                "force_reprocess": {
                    "type": "boolean",
                    "description": "Whether to force reprocessing if SourceData already exists",
                    "default": False
                },
                "link": {
                    "type": "string",
                    "description": "Document URL/link",
                    "default": None
                },
                "content": {
                    "type": "string",
                    "description": "Direct text content for text-based processing (bypasses file extraction)"
                }
            },
            "anyOf": [
                {"required": ["file_path", "topic_name"]},
                {"required": ["file_content", "file_name", "topic_name"]},
                {"required": ["content", "file_name", "topic_name"]}
            ]
        }
    
    @property
    def output_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_data_id": {
                    "type": "string",
                    "description": "ID of created SourceData record"
                },
                "content_hash": {
                    "type": "string",
                    "description": "SHA-256 hash of extracted content"
                },
                "content_size": {
                    "type": "integer",
                    "description": "Size of extracted content in bytes"
                },
                "source_type": {
                    "type": "string",
                    "description": "Detected content type (pdf, txt, etc.)"
                },
                "reused_existing": {
                    "type": "boolean",
                    "description": "Whether existing SourceData was reused"
                },
                "status": {
                    "type": "string",
                    "description": "Processing status"
                }
            }
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        topic_name = input_data.get("topic_name")
        if not topic_name or not isinstance(topic_name, str):
            return False
            
        # Check if we have at least one valid input method
        file_path = input_data.get("file_path")
        file_content = input_data.get("file_content")
        content = input_data.get("content")
        
        if file_path:
            if not Path(file_path).exists():
                return False
        elif file_content:
            if not input_data.get("file_name"):
                return False
        elif content:
            if not input_data.get("file_name"):
                return False
        else:
            return False  # No valid input provided
            
        return True
    
    def _extract_content_in_memory(self, file_content: bytes, file_name: str, file_type: str = None) -> Dict[str, Any]:
        """Extract content from file bytes in memory."""
        try:
            file_extension = Path(file_name).suffix.lower()
            
            if not file_type:
                # Infer file type from extension
                if file_extension == ".pdf":
                    file_type = "application/pdf"
                elif file_extension == ".md":
                    file_type = "text/markdown"
                elif file_extension == ".txt":
                    file_type = "text/plain"
                elif file_extension == ".sql":
                    file_type = "text/sql"
                else:
                    file_type = "text/plain"
            
            if file_type.startswith("text/") or file_extension in [".md", ".txt", ".sql"]:
                # Text-based content
                try:
                    content = file_content.decode('utf-8')
                except UnicodeDecodeError:
                    content = file_content.decode('utf-8', errors='ignore')
                
                return {
                    "status": "success",
                    "content": content,
                    "file_type": file_extension.lstrip('.')
                }
            elif file_type == "application/pdf" or file_extension == ".pdf":
                # For PDF, we'll use a simplified approach since pymupdf requires file path
                # This is a limitation - we might need to use BytesIO or similar
                # For now, we'll treat it as text extraction
                try:
                    import pymupdf
                    import tempfile
                    
                    # Temporarily write to memory file for PDF processing
                    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                        tmp_file.write(file_content)
                        tmp_file.flush()
                        
                        try:
                            doc = pymupdf.open(tmp_file.name)
                            content = ""
                            for page in doc:
                                content += page.get_text()
                            doc.close()
                            
                            return {
                                "status": "success",
                                "content": content,
                                "file_type": "pdf"
                            }
                        finally:
                            # Clean up temp file
                            try:
                                os.unlink(tmp_file.name)
                            except:
                                pass
                                
                except ImportError:
                    # Fallback to text extraction
                    return {
                        "status": "success",
                        "content": file_content.decode('utf-8', errors='ignore'),
                        "file_type": "pdf"
                    }
            else:
                # Default to text extraction
                return {
                    "status": "success",
                    "content": file_content.decode('utf-8', errors='ignore'),
                    "file_type": "unknown"
                }
                
        except Exception as e:
            self.logger.error(f"Error extracting content from file bytes: {e}")
            return {
                "status": "error",
                "error": str(e),
                "content": "",
                "file_type": "unknown"
            }

    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute ETL processing for a single document.
        
        Args:
            input_data: Dictionary containing:
                - file_path: Path to the document file (legacy)
                - file_content: Base64 encoded file content
                - file_name: Original filename
                - file_type: MIME type
                - content: Direct text content
                - topic_name: Topic name for grouping
                - metadata: Optional custom metadata
                - force_reprocess: Whether to force reprocessing
                - link: Optional document link/URL
                
        Returns:
            ToolResult with SourceData processing results
        """
        try:
            topic_name = input_data["topic_name"]
            metadata = input_data.get("metadata", {})
            force_reprocess = input_data.get("force_reprocess", False)
            link = input_data.get("link")
            
            # Determine input method
            file_path = input_data.get("file_path")
            file_content = input_data.get("file_content")
            direct_content = input_data.get("content")
            file_name = input_data.get("file_name", "unknown")
            file_type = input_data.get("file_type")
            
            if file_path:
                # Legacy file path processing
                file_path_obj = Path(file_path)
                original_filename = input_data.get("original_filename", file_path_obj.name)
                link = link or f"file://{file_path}"
                
                with open(file_path, 'rb') as f:
                    file_content_bytes = f.read()
                    file_hash = hashlib.sha256(file_content_bytes).hexdigest()
                    
                # Extract content using existing method
                extraction_result = extract_source_data(str(file_path))
                content = extraction_result.get("content", "")
                source_type = extraction_result.get("file_type", "unknown")
                
            elif file_content:
                # Base64 encoded file content processing
                try:
                    file_content_bytes = base64.b64decode(file_content)
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error_message=f"Invalid base64 encoding: {e}"
                    )
                
                original_filename = file_name
                link = link or f"inline://{file_name}"
                file_hash = hashlib.sha256(file_content_bytes).hexdigest()
                
                # Extract content in memory
                extraction_result = self._extract_content_in_memory(
                    file_content_bytes, file_name, file_type
                )
                
                if extraction_result["status"] != "success":
                    return ToolResult(
                        success=False,
                        error_message=f"Content extraction failed: {extraction_result.get('error', 'Unknown error')}"
                    )
                
                content = extraction_result["content"]
                source_type = extraction_result["file_type"]
                
            elif direct_content:
                # Direct text content processing
                content = direct_content
                original_filename = file_name
                link = link or f"inline://{file_name}"
                file_content_bytes = content.encode('utf-8')
                file_hash = hashlib.sha256(file_content_bytes).hexdigest()
                source_type = "text"
                
            else:
                return ToolResult(
                    success=False,
                    error_message="No valid input provided (file_path, file_content, or content)"
                )
            
            self.logger.info(f"Starting ETL processing for file: {original_filename}")
            
            # Normalize content type
            if source_type == "pdf":
                source_type = "application/pdf"
            elif source_type == "md":
                source_type = "text/markdown"
            elif source_type == "txt":
                source_type = "text/plain"
            elif source_type == "text":
                source_type = "text/plain"
            else:
                source_type = f"text/{source_type}" if source_type else "text/plain"
            
            with self.session_factory() as db:
                # Check if we already have this content
                content_store = db.query(ContentStore).filter_by(
                    content_hash=file_hash
                ).first()
                
                # Create or get RawDataSource record
                # For in-memory processing, use the link as file_path identifier
                file_path_str = str(file_path) if file_path else link
                raw_data_source = db.query(RawDataSource).filter_by(
                    file_path=file_path_str,
                    topic_name=topic_name
                ).first()
                
                if not raw_data_source:
                    raw_data_source = RawDataSource(
                        file_path=file_path_str,
                        topic_name=topic_name,
                        original_filename=original_filename,
                        metadata=metadata,
                        status="pending"
                    )
                    db.add(raw_data_source)
                    db.flush()
                
                # Check if already processed and not forcing reprocess
                if not force_reprocess:
                    existing_source_data = db.query(SourceData).filter(
                        SourceData.raw_data_source_id == raw_data_source.id
                    ).first()
                    
                    if existing_source_data:
                        self.logger.info(f"SourceData already exists for file: {original_filename}")
                        return ToolResult(
                            success=True,
                            data={
                                "source_data_id": existing_source_data.id,
                                "content_hash": existing_source_data.content_hash,
                                "reused_existing": True,
                                "status": "already_processed"
                            },
                            metadata={
                                "file_path": file_path_str,
                                "topic_name": topic_name,
                                "file_size": len(file_content_bytes)
                            }
                        )
                
                # Update status to processing
                raw_data_source.status = "etl_processing"
                db.commit()
                
                # Content is already extracted above, no need for extract_source_data call
                
                # Create or update ContentStore
                if not content_store:
                    content_store = ContentStore(
                        content_hash=file_hash,
                        content=content,
                        content_size=len(content),
                        content_type=source_type,
                        name=Path(original_filename).stem,
                        link=link
                    )
                    db.add(content_store)
                    db.flush()
                
                # Create SourceData record
                source_data = SourceData(
                    name=original_filename,
                    topic_name=topic_name,
                    raw_data_source_id=raw_data_source.id,
                    content_hash=file_hash,
                    link=link,
                    source_type=source_type,
                    attributes={
                        **metadata,
                        "file_path": file_path_str,
                        "original_filename": original_filename,
                        "file_size": len(file_content_bytes),
                        "extraction_method": "DocumentETLTool"
                    },
                    status="created"
                )
                
                # Update RawDataSource status
                raw_data_source.status = "etl_completed"
                
                db.add(source_data)
                db.commit()
                db.refresh(source_data)
                
                self.logger.info(f"ETL processing completed for file: {original_filename}")
                
                return ToolResult(
                    success=True,
                    data={
                        "source_data_id": source_data.id,
                        "content_hash": file_hash,
                        "content_size": len(content),
                        "source_type": source_type,
                        "reused_existing": False,
                        "status": "created"
                    },
                    metadata={
                        "file_path": file_path_str,
                        "topic_name": topic_name,
                        "file_size": len(file_content_bytes),
                        "content_type": source_type
                    }
                )
                
        except Exception as e:
            self.logger.error(f"ETL processing failed: {e}")
            return ToolResult(
                success=False,
                error_message=str(e)
            )


# Register the tool
from tools.base import TOOL_REGISTRY
TOOL_REGISTRY.register(DocumentETLTool())