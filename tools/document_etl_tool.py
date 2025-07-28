"""
DocumentETLTool: Processes a single raw document file.

- Purpose: To process a single raw document file
- Input: Raw file (e.g., PDF, TXT), Topic ID
- Output: Structured SourceData (text, initial entities, etc.)
- Maps to: KnowledgeBuilder.build_from_file logic
"""

import hashlib
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from tools.base import BaseTool, ToolResult
from etl.extract import extract_source_data
from knowledge_graph.models import RawDataSource, SourceData, ContentStore
from setting.db import SessionLocal


class DocumentETLTool(BaseTool):
    """
    Processes raw document files into structured SourceData.
    
    This tool takes raw files and topic information, extracts content,
    and creates structured SourceData for further processing.
    Supports both single file and batch file processing.
    
    Input Schema (Single file):
        file_path (str): Path to the document file
        topic_name (str): Topic name for grouping documents
        metadata (dict, optional): Custom metadata to attach
        force_reprocess (bool, optional): Force reprocessing even if already processed
        link (str, optional): Document URL/link
        original_filename (str, optional): Original filename if different from file_path
    
    Input Schema (Batch files):
        files (list): List of file objects with path, metadata, link, filename properties
        topic_name (str): Topic name for grouping documents
        force_reprocess (bool, optional): Force reprocessing even if already processed
    
    Output Schema:
        source_data_ids (list[str]): IDs of created SourceData records
        results (list[dict]): Individual processing results for each file
        batch_summary (dict): Summary of batch processing
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
            "oneOf": [
                {
                    "title": "Single File Processing",
                    "required": ["file_path", "topic_name"],
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the document file"
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
                        "force_regenerate": {
                            "type": "boolean",
                            "description": "Whether to force regeneration if SourceData already exists",
                            "default": False
                        },
                        "link": {
                            "type": "string",
                            "description": "Document URL/link",
                            "default": None
                        },
                        "original_filename": {
                            "type": "string",
                            "description": "Original filename if different from file_path",
                            "default": None
                        }
                    }
                },
                {
                    "title": "Batch File Processing",
                    "required": ["files", "topic_name"],
                    "properties": {
                        "files": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["path"],
                                "properties": {
                                    "path": {
                                        "type": "string",
                                        "description": "Path to the document file"
                                    },
                                    "metadata": {
                                        "type": "object",
                                        "description": "Custom metadata to attach to this document",
                                        "default": {}
                                    },
                                    "link": {
                                        "type": "string",
                                        "description": "Document URL/link",
                                        "default": None
                                    },
                                    "filename": {
                                        "type": "string",
                                        "description": "Original filename if different from path"
                                    }
                                }
                            },
                            "description": "List of files to process"
                        },
                        "topic_name": {
                            "type": "string",
                            "description": "Topic name for grouping documents"
                        },
                        "force_regenerate": {
                            "type": "boolean",
                            "description": "Whether to force regeneration if SourceData already exists",
                            "default": False
                        }
                    }
                }
            ],
            "properties": {
                "force_regenerate": {
                    "type": "boolean",
                    "description": "Whether to force regeneration if SourceData already exists",
                    "default": False
                }
            }
        }
    
    @property
    def output_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_data_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "IDs of created SourceData records"
                },
                "results": {
                    "type": "array",
                    "items": {
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
                            },
                            "file_path": {
                                "type": "string",
                                "description": "Original file path"
                            }
                        }
                    },
                    "description": "Individual processing results for each file"
                },
                "batch_summary": {
                    "type": "object",
                    "properties": {
                        "total_files": {"type": "integer"},
                        "processed_files": {"type": "integer"},
                        "reused_files": {"type": "integer"},
                        "failed_files": {"type": "integer"}
                    },
                    "description": "Summary of batch processing"
                }
            }
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input parameters."""
        topic_name = input_data.get("topic_name")
        if not topic_name or not isinstance(topic_name, str):
            return False
        
        # Single file validation
        if "file_path" in input_data:
            file_path = input_data.get("file_path")
            if not file_path or not Path(file_path).exists():
                return False
        
        # Batch file validation
        if "files" in input_data:
            files = input_data.get("files", [])
            if not files or not isinstance(files, list):
                return False
            
            for file_info in files:
                if not isinstance(file_info, dict):
                    return False
                file_path = file_info.get("path")
                if not file_path or not Path(file_path).exists():
                    return False
        
        return True
    
    def execute(self, input_data: Dict[str, Any]) -> ToolResult:
        """
        Execute ETL processing for documents (single or batch).
        
        Args:
            input_data: Dictionary containing either:
                - Single file: file_path + topic_name + optional metadata
                - Batch files: files array + topic_name + optional metadata
                - force_regenerate: Whether to force regeneration
                
        Returns:
            ToolResult with batch processing results
        """
        try:
            topic_name = input_data["topic_name"]
            force_regenerate = input_data.get("force_regenerate", False)
            
            # Determine processing mode
            if "files" in input_data:
                # Batch processing
                files = input_data["files"]
                return self._process_batch_files(files, topic_name, force_regenerate)
            else:
                # Single file processing (backward compatibility)
                file_path = Path(input_data["file_path"])
                metadata = input_data.get("metadata", {})
                link = input_data.get("link", f"file://{file_path}")
                original_filename = input_data.get("original_filename", file_path.name)
                
                file_info = {
                    "path": str(file_path),
                    "metadata": metadata,
                    "link": link,
                    "filename": original_filename
                }
                
                result = self._process_single_file(file_info, topic_name, force_regenerate)
                
                # Convert single file result to new format for backward compatibility
                if result.success:
                    return ToolResult(
                        success=True,
                        data={
                            "source_data_ids": [result.data["source_data_id"]],
                            "results": [result.data],
                            "batch_summary": {
                                "total_files": 1,
                                "processed_files": 1,
                                "reused_files": 1 if result.data.get("reused_existing") else 0,
                                "failed_files": 0
                            }
                        },
                        metadata=result.metadata
                    )
                else:
                    return result
                
        except Exception as e:
            self.logger.error(f"ETL processing failed: {e}")
            return ToolResult(
                success=False,
                error_message=str(e)
            )

    def _process_batch_files(self, files: List[Dict[str, Any]], topic_name: str, force_regenerate: bool = False) -> ToolResult:
        """Process multiple files in batch."""
        results = []
        source_data_ids = []
        
        total_files = len(files)
        processed_files = 0
        reused_files = 0
        failed_files = 0
        
        self.logger.info(f"Starting batch ETL processing for {total_files} files")
        
        for file_info in files:
            try:
                file_result = self._process_single_file(file_info, topic_name, force_regenerate)
                
                if file_result.success:
                    source_data_id = file_result.data.get("source_data_id")
                    if source_data_id:
                        source_data_ids.append(source_data_id)
                    
                    results.append({
                        **file_result.data,
                        "file_path": file_info.get("path"),
                        "status": "success"
                    })
                    
                    if file_result.data.get("reused_existing"):
                        reused_files += 1
                    else:
                        processed_files += 1
                        
                else:
                    failed_files += 1
                    results.append({
                        "file_path": file_info.get("path"),
                        "status": "failed",
                        "error": file_result.error_message
                    })
                    
            except Exception as e:
                failed_files += 1
                results.append({
                    "file_path": file_info.get("path"),
                    "status": "failed",
                    "error": str(e)
                })
        
        self.logger.info(
            f"Batch ETL completed: {processed_files} processed, {reused_files} reused, {failed_files} failed"
        )
        
        return ToolResult(
            success=True,
            data={
                "source_data_ids": source_data_ids,
                "results": results,
                "batch_summary": {
                    "total_files": total_files,
                    "processed_files": processed_files,
                    "reused_files": reused_files,
                    "failed_files": failed_files
                }
            },
            metadata={
                "topic_name": topic_name,
                "total_files": total_files
            }
        )

    def _process_single_file(self, file_info: Dict[str, Any], topic_name: str, force_regenerate: bool = False) -> ToolResult:
        """Process a single file."""
        try:
            file_path = Path(file_info["path"])
            metadata = file_info.get("metadata", {})
            link = file_info.get("link", f"file://{file_path}")
            original_filename = file_info.get("filename", file_path.name)
            
            self.logger.info(f"Starting ETL processing for file: {file_path}")
            
            # Check if file exists
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error_message=f"File not found: {file_path}"
                )
            
            # Calculate file hash for deduplication
            with open(file_path, 'rb') as f:
                file_content = f.read()
                file_hash = hashlib.sha256(file_content).hexdigest()
            
            with self.session_factory() as db:
                # Check if we already have this content
                content_store = db.query(ContentStore).filter_by(
                    content_hash=file_hash
                ).first()
                
                # Create or get RawDataSource record
                raw_data_source = db.query(RawDataSource).filter_by(
                    file_path=str(file_path),
                    topic_name=topic_name
                ).first()
                
                if not raw_data_source:
                    raw_data_source = RawDataSource(
                        file_path=str(file_path),
                        topic_name=topic_name,
                        original_filename=original_filename,
                        metadata=metadata,
                        status="pending"
                    )
                    db.add(raw_data_source)
                    db.flush()
                
                # Check if already processed and not forcing reprocess
                if not force_regenerate:
                    existing_source_data = db.query(SourceData).filter(
                        SourceData.raw_data_source_id == raw_data_source.id
                    ).first()
                    
                    if existing_source_data:
                        self.logger.info(f"SourceData already exists for file: {file_path}")
                        return ToolResult(
                            success=True,
                            data={
                                "source_data_id": existing_source_data.id,
                                "content_hash": existing_source_data.content_hash,
                                "content_size": len(existing_source_data.effective_content or ""),
                                "source_type": existing_source_data.source_type,
                                "reused_existing": True,
                                "status": "already_processed"
                            },
                            metadata={
                                "file_path": str(file_path),
                                "topic_name": topic_name,
                                "file_size": len(file_content)
                            }
                        )
                
                # Update status to processing
                raw_data_source.status = "etl_processing"  # type: ignore
                db.commit()
                
                # Extract content from file
                try:
                    extraction_result = extract_source_data(str(file_path))
                    # Handle both string and dict return types safely
                    if isinstance(extraction_result, dict):
                        content = extraction_result.get("content", "")
                        source_type = extraction_result.get("file_type", "text/plain")
                    else:
                        content = str(extraction_result)
                        source_type = "text/plain"
                    # Normalize content type to match job standards
                    if source_type == "pdf":
                        source_type = "application/pdf"
                    elif source_type == "md":
                        source_type = "text/markdown"
                    elif source_type == "txt":
                        source_type = "text/plain"
                    elif source_type == "sql":
                        source_type = "application/sql"
                    else:
                        source_type = "text/plain"
                except Exception as e:
                    self.logger.error(f"Failed to extract content from {file_path}: {e}")
                    # Update status to failed
                    raw_data_source.status = "etl_failed"  # type: ignore
                    db.commit()
                    return ToolResult(
                        success=False,
                        error_message=f"Content extraction failed: {str(e)}"
                    )
                
                # Create or update ContentStore
                if not content_store:
                    content_store = ContentStore(
                        content_hash=file_hash,
                        content=content,
                        content_size=len(content),
                        content_type=source_type,
                        name=file_path.stem,
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
                        "file_path": str(file_path),
                        "original_filename": original_filename,
                        "file_size": len(file_content),
                        "extraction_method": "DocumentETLTool"
                    },
                    status="created"
                )
                
                # Update RawDataSource status
                raw_data_source.status = "etl_completed"  # type: ignore
                
                db.add(source_data)
                db.commit()
                db.refresh(source_data)
                
                self.logger.info(f"ETL processing completed for file: {file_path}")
                
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
                        "file_path": str(file_path),
                        "topic_name": topic_name,
                        "file_size": len(file_content),
                        "content_type": source_type
                    }
                )
                
        except Exception as e:
            self.logger.error(f"ETL processing failed: {e}")
            return ToolResult(
                success=False,
                error_message=str(e)
            )


# Register the tool - will be handled by orchestrator initialization