"""
API Integration for flexible pipeline orchestration.

This module provides the integration layer for the /api/v1/save endpoint
to use the tool-based pipeline system as described in the design document.
"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid

from tools.orchestrator import PipelineOrchestrator
from tools.base import ToolResult

logger = logging.getLogger(__name__)


class PipelineAPIIntegration:
    """
    API integration layer for pipeline-based processing.
    
    Transforms the /api/v1/save endpoint into a flexible pipeline orchestrator
    that supports both explicit pipeline configuration and intelligent defaults.
    """
    
    def __init__(self, session_factory=None):
        self.orchestrator = PipelineOrchestrator(session_factory)
        self.logger = logging.getLogger(__name__)
    
    def process_request(self, request_data: Dict[str, Any], files: List[Dict[str, Any]] = None, 
                       execution_id: Optional[str] = None) -> ToolResult:
        """
        Process a knowledge ingestion request using pipeline orchestration.
        
        Args:
            request_data: Standard API request data
            files: List of file information (each with path, metadata, etc. Optional)
            execution_id: Optional execution ID for tracking
            
        Returns:
            ToolResult with processing results
        """
        execution_id = execution_id or str(uuid.uuid4())
        
        # Prepare context for pipeline execution
        context = self._prepare_context(request_data, files)
        
        # Execute pipeline based on process strategy
        return self.orchestrator.execute_with_process_strategy(context, execution_id)
    
    def _prepare_context(self, request_data: Dict[str, Any], files: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Prepare context for pipeline execution from API request.
        
        Args:
            request_data: API request data
            files: List of file information (optional)
            
        Returns:
            Context dictionary for pipeline execution
        """
        metadata = request_data.get("metadata", {})
        
        # Map SmartSave API parameters to tool system parameters
        context = {
            "target_type": request_data.get("target_type", "knowledge_graph"),
            "process_strategy": request_data.get("process_strategy", {}),
            "metadata": metadata,
            "files": files or [],
            "llm_config": request_data.get("llm_config"),
            "embedding_config": request_data.get("embedding_config"),
            "force_regenerate": request_data.get("force_regenerate", False),
            "topic_name": metadata.get("topic_name"),
            "link": metadata.get("link"),
            "database_uri": metadata.get("database_uri")
        }
        
        # Handle file-specific parameters based on number of files
        if files:
            file_count = len(files)
            
            # Single file processing
            if file_count == 1:
                file_info = files[0]
                
                # Support both legacy file_path and new in-memory formats
                if "path" in file_info:
                    context["file_path"] = file_info.get("path")
                    context["original_filename"] = file_info.get("filename")
                elif "file_content" in file_info:
                    # In-memory file processing
                    context["file_content"] = file_info.get("file_content")
                    context["file_name"] = file_info.get("file_name")
                    context["file_type"] = file_info.get("file_type")
                elif "content" in file_info:
                    # Direct text content processing
                    context["content"] = file_info.get("content")
                    context["file_name"] = file_info.get("file_name")
                    context["file_type"] = file_info.get("file_type")
            
            # Multiple files processing
            else:
                # Set file count for pipeline selection
                context["metadata"]["file_count"] = file_count
                context["metadata"]["is_new_topic"] = metadata.get("is_new_topic", False)
                
                # Provide individual file information for batch processing
                context["file_paths"] = [f.get("path") for f in files if "path" in f]
                context["file_contents"] = [
                    {
                        "file_content": f.get("file_content"),
                        "file_name": f.get("file_name"),
                        "file_type": f.get("file_type")
                    }
                    for f in files
                    if "file_content" in f
                ]
                
        return context
    
    def process_single_file(self, file_path: str, topic_name: str, metadata: Dict[str, Any] = None,
                          llm_config=None, embedding_config=None) -> ToolResult:
        """
        Process a single file using the appropriate pipeline.
        
        Args:
            file_path: Path to the file to process
            topic_name: Topic name for grouping
            metadata: Optional metadata for the file
            llm_client: LLM client instance
            embedding_func: Embedding function
            
        Returns:
            ToolResult with processing results
        """
        context = {
            "file_path": file_path,
            "topic_name": topic_name,
            "metadata": metadata or {},
            "llm_config": llm_config,
            "embedding_config": embedding_config
        }
        
        # Determine if this is a new topic or existing
        from setting.db import SessionLocal
        from knowledge_graph.models import SourceData
        
        with SessionLocal() as db:
            existing_count = db.query(SourceData).filter(
                SourceData.topic_name == topic_name
            ).count()
            
            is_new_topic = existing_count == 0
            context["metadata"]["is_new_topic"] = is_new_topic
        
        return self.orchestrator.execute_with_process_strategy(context)
    
    def process_batch_files(self, file_paths: List[str], topic_name: str, metadata: Dict[str, Any] = None,
                          llm_config=None, embedding_config=None) -> ToolResult:
        """
        Process multiple files using batch pipeline.
        
        Args:
            file_paths: List of file paths to process
            topic_name: Topic name for grouping
            metadata: Optional metadata for the files
            llm_client: LLM client instance
            embedding_func: Embedding function
            
        Returns:
            ToolResult with processing results
        """
        files = [{"path": fp, "metadata": {}} for fp in file_paths]
        
        context = {
            "files": files or [],
            "topic_name": topic_name,
            "metadata": metadata or {},
            "llm_config": llm_config,
            "embedding_config": embedding_config
        }
        
        return self.orchestrator.execute_with_process_strategy(context)


# Example usage
if __name__ == "__main__":
    # Example of direct pipeline usage
    integration = PipelineAPIIntegration()
    
    # Example 1: Explicit pipeline configuration
    explicit_request = {
        "target_type": "knowledge_graph",
        "metadata": {"topic_name": "New Topic"},
        "process_strategy": {
            "pipeline": ["etl", "blueprint_gen", "graph_build"]
        },
        "file_path": "/path/to/document.pdf"
    }
    
    # Example 2: Default pipeline selection
    default_request = {
        "target_type": "knowledge_graph",
        "metadata": {"topic_name": "Existing Topic", "is_new_topic": False},
        "file_path": "/path/to/document.pdf"
    }