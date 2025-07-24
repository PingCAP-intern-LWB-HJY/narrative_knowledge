"""
Pipeline Orchestrator for dynamic tool sequencing.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid
from pathlib import Path

from tools.base import ToolResult
from tools.base import TOOL_REGISTRY
from setting.db import SessionLocal


class PipelineOrchestrator:
    """
    Orchestrates tool execution into dynamic pipelines.
    
    Supports main scenarios:
    1. Adding single document to existing topic
    2. Adding batch documents to existing topic  
    3. Creating new topic with batch documents
    """
    
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or SessionLocal
        self.logger = logging.getLogger(__name__)
        
        # Define standard pipelines using tool keys
        self.standard_pipelines = {
            # Knowledge graph pipelines
            "single_doc_existing_topic": ["etl", "graph_build"],
            "batch_doc_existing_topic": ["etl", "blueprint_gen", "graph_build"],
            "new_topic_batch": ["etl", "blueprint_gen", "graph_build"],
            "text_to_graph": ["graph_build"],
            
            # Memory pipelines
            "memory_direct_graph": ["memory_graph_build"],  # Direct memory processing with graph building
            "memory_single": ["memory_graph_build"]  # Single memory processing
        }
        
        # Tool key to name mapping
        self.tool_key_mapping = {
            "etl": "DocumentETLTool",
            "blueprint_gen": "BlueprintGenerationTool", 
            "graph_build": "GraphBuildTool",
            "memory_graph_build": "MemoryGraphBuildTool"
        }
    
    def execute_pipeline(self, pipeline_name: str, context: Dict[str, Any], execution_id: Optional[str] = None) -> ToolResult:
        """
        Execute a predefined pipeline.
        
        Args:
            pipeline_name: Name of the predefined pipeline
            context: Context data for pipeline execution
            execution_id: Optional execution ID for tracking
            
        Returns:
            ToolResult with pipeline execution results
        """
        execution_id = execution_id or str(uuid.uuid4())
        
        if pipeline_name not in self.standard_pipelines:
            return ToolResult(
                success=False,
                error_message=f"Pipeline '{pipeline_name}' not found"
            )
        
        tool_keys = self.standard_pipelines[pipeline_name]
        tools = [self.tool_key_mapping[key] for key in tool_keys]
        return self.execute_custom_pipeline(tools, context, execution_id)
    
    def execute_custom_pipeline(self, tools: List[str], context: Dict[str, Any], execution_id: Optional[str] = None) -> ToolResult:
        """
        Execute a custom pipeline with specific tool sequence.
        
        Supports both single-file and batch processing.
        
        Args:
            tools: List of tool names to execute in sequence
            context: Context data for pipeline execution
            execution_id: Optional execution ID for tracking
            
        Returns:
            ToolResult with pipeline execution results
        """
        execution_id = execution_id or str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        self.logger.info(f"Starting pipeline execution: {execution_id} - {tools}")
        
        # Handle batch processing for multiple files
        files = context.get("files", [])
        file_contents = context.get("file_contents", [])
        file_paths = context.get("file_paths", [])
        
        # Determine if we have multiple files to process
        multiple_files = len(files) > 1 or len(file_contents) > 1 or len(file_paths) > 1
        
        if multiple_files and "etl" in [self.tool_key_mapping.get(tool, tool) for tool in tools]:
            return self._execute_batch_pipeline(tools, context, execution_id)
        
        # Standard single-file processing - delegate to helper method
        result = self._execute_single_file_pipeline(tools, context, execution_id)
        
        # Add duration and pipeline info for consistency
        if result.success:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            self.logger.info(f"Pipeline execution completed: {execution_id} in {duration:.2f}s")
            
            # Ensure the result has the expected structure
            if "results" in result.data:
                result.data["pipeline"] = tools
                result.data["duration_seconds"] = duration
            
        return result
    
    def select_default_pipeline(self, target_type: str, topic_name: str, file_count: int, is_new_topic: bool, 
                              input_type: str = "document", file_extension: str = None) -> str:
        """
        Select appropriate default pipeline based on context.
        
        Args:
            target_type: Target type (knowledge_graph, personal_memory)
            topic_name: Topic name
            file_count: Number of files to process
            is_new_topic: Whether this is a new topic
            input_type: Type of input (document, dialogue, text)
            file_extension: File extension for document processing
            
        Returns:
            Name of the default pipeline to use
        """
        
        # Memory pipeline for dialogue history/chat
        if target_type == "personal_memory" or input_type == "dialogue":
            if input_type == "dialogue":
                return "memory_direct_graph"  # Direct graph extraction from dialogue
            else:
                return "memory_single"  # Single memory processing
        
        # Knowledge graph pipeline for documents
        if target_type == "knowledge_graph":
            # Document processing pipeline
            if input_type == "document":
                if is_new_topic:
                    return "new_topic_batch"
                elif file_count == 1:
                    return "single_doc_existing_topic"
                else:
                    return "batch_doc_existing_topic"
            elif input_type == "text":
                return "text_to_graph"  # Direct text processing
        
        # Default fallback
        return "single_doc_existing_topic"
    
    def _prepare_tool_input(self, tool_name: str, context: Dict[str, Any], 
                           previous_results: Dict[str, ToolResult]) -> Dict[str, Any]:
        """Prepare input for a specific tool based on context and previous results."""
        
        # Map tool names to keys for consistent handling
        tool_key = None
        for key, name in self.tool_key_mapping.items():
            if name == tool_name:
                tool_key = key
                break
        
        if tool_key == "etl":
            return {
                "file_path": context.get("file_path"),
                "topic_name": context.get("topic_name"),
                "metadata": context.get("metadata", {}),
                "force_regenerate": context.get("force_regenerate", False),
                "link": context.get("link"),
                "original_filename": context.get("original_filename")
            }
        
        elif tool_key == "blueprint_gen":
            # Collect source_data_ids from context (accumulated from ETL results)
            source_data_ids = context.get("source_data_ids", [])
            
            # If no accumulated IDs, check for single ID
            if not source_data_ids and context.get("source_data_id"):
                source_data_ids = [context.get("source_data_id")]
            
            # Handle topic-based processing when no specific IDs provided
            if not source_data_ids and context.get("topic_name"):
                return {
                    "topic_name": context.get("topic_name"),
                    "source_data_ids": source_data_ids or None,
                    "force_regenerate": context.get("force_regenerate", False),
                    "llm_config": context.get("llm_config"),
                    "embedding_config": context.get("embedding_config")
                }
            
            return {
                "topic_name": context.get("topic_name"),
                "source_data_ids": source_data_ids,
                "force_regenerate": context.get("force_regenerate", False),
                "llm_config": context.get("llm_config"),
                "embedding_config": context.get("embedding_config")
            }
        
        elif tool_key == "graph_build":
            topic_name = context.get("topic_name")
            
            # Check if we have ETL and/or Blueprint from pipeline
            has_etl = any(self.tool_key_mapping.get("etl") in tools for tools in [previous_results.keys()])
            has_blueprint = any(self.tool_key_mapping.get("blueprint_gen") in tools for tools in [previous_results.keys()])
            
            # Case 1: We have ETL/Blueprint tools in pipeline (with results)
            if has_etl or has_blueprint:
                source_data_ids = context.get("source_data_ids", [])
                blueprint_id = context.get("blueprint_id")
                
                # Fill missing IDs from context
                if not source_data_ids and context.get("source_data_id"):
                    source_data_ids = [context.get("source_data_id")]
                
                if source_data_ids and blueprint_id:
                    return {
                        "source_data_ids": source_data_ids,
                        "blueprint_id": blueprint_id,
                        "force_regenerate": context.get("force_regenerate", False),
                        "llm_config": context.get("llm_config"),
                        "embedding_config": context.get("embedding_config")
                    }
                elif source_data_ids and len(source_data_ids) == 1:
                    return {
                        "source_data_id": source_data_ids[0],
                        "force_regenerate": context.get("force_regenerate", False),
                        "llm_config": context.get("llm_config"),
                        "embedding_config": context.get("embedding_config")
                    }
                else:
                    return {
                        "topic_name": topic_name,
                        "force_regenerate": context.get("force_regenerate", False),
                        "llm_config": context.get("llm_config"),
                        "embedding_config": context.get("embedding_config")
                    }
            
            # Case 2: No ETL/Blueprint (graph_build-only pipelines)
            else:
                # Default to topic-based processing
                return {
                    "topic_name": topic_name,
                    "force_regenerate": context.get("force_regenerate", False),
                    "llm_config": context.get("llm_config"),
                    "embedding_config": context.get("embedding_config")
                }
        
        return context.copy()
    
    def _update_context(self, tool_name: str, context: Dict[str, Any], result: ToolResult) -> Dict[str, Any]:
        """Update context with results from a tool."""
        updated_context = context.copy()
        
        # Map tool name to key
        tool_key = None
        for key, name in self.tool_key_mapping.items():
            if name == tool_name:
                tool_key = key
                break
        
        if tool_key == "etl" and result.success:
            source_data_id = result.data.get("source_data_id")
            if source_data_id:
                # Maintain both singular and plural forms for consistency
                updated_context["source_data_id"] = source_data_id
                if "source_data_ids" not in updated_context:
                    updated_context["source_data_ids"] = []
                updated_context["source_data_ids"].append(source_data_id)
            
            updated_context["topic_name"] = result.metadata.get("topic_name")
        
        elif tool_key == "blueprint_gen" and result.success:
            updated_context["blueprint_id"] = result.data.get("blueprint_id")
            updated_context["topic_name"] = result.metadata.get("topic_name")
        
        return updated_context
    
    def _execute_batch_pipeline(self, tools: List[str], context: Dict[str, Any], execution_id: str) -> ToolResult:
        """
        Execute pipeline for multiple files in batch.
        
        Processes each file sequentially through the pipeline, accumulating results.
        
        Args:
            tools: List of tool names to execute
            context: Context containing multiple files
            execution_id: Execution ID for tracking
            
        Returns:
            ToolResult with aggregated batch processing results
        """
        self.logger.info(f"Starting batch pipeline execution: {execution_id} - {tools}")
        
        # Extract file information from context
        files = context.get("files", [])
        file_contents = context.get("file_contents", [])
        file_paths = context.get("file_paths", [])
        topic_name = context.get("topic_name")
        
        # Build list of individual file contexts
        individual_files = []
        
        # Handle file_paths
        for path in file_paths:
            individual_files.append({"file_path": path})
        
        # Handle file_contents
        for file_info in file_contents:
            individual_files.append(file_info)
        
        # Handle files list (legacy format)
        for file_info in files:
            if "path" in file_info:
                individual_files.append({"file_path": file_info["path"]})
            elif "file_content" in file_info:
                individual_files.append(file_info)
            elif "content" in file_info:
                individual_files.append(file_info)
        
        if not individual_files:
            return ToolResult(
                success=False,
                error_message="No valid files found for batch processing"
            )
        
        total_files = len(individual_files)
        self.logger.info(f"Processing {total_files} files in batch")
        
        # Process each file through the pipeline
        all_results = []
        accumulated_source_data_ids = []
        
        for file_index, file_context in enumerate(individual_files):
            file_execution_id = f"{execution_id}_file_{file_index}"
            
            # Create individual context for this file
            individual_context = context.copy()
            individual_context.update(file_context)
            individual_context["metadata"] = context.get("metadata", {}).copy()
            
            # Add file-specific metadata
            if "file_name" in file_context:
                individual_context["metadata"]["original_filename"] = file_context["file_name"]
            
            # Execute pipeline for this single file
            try:
                file_result = self._execute_single_file_pipeline(
                    tools, individual_context, file_execution_id
                )
                
                if file_result.success:
                    # Extract source_data_id from ETL results for blueprint generation
                    if "etl" in file_result.data.get("results", {}):
                        source_data_id = file_result.data["results"]["etl"].data.get("source_data_id")
                        if source_data_id:
                            accumulated_source_data_ids.append(source_data_id)
                    
                    all_results.append({
                        "file_index": file_index,
                        "file_name": file_context.get("file_name") or Path(file_context.get("file_path", "")).name,
                        "results": file_result.data.get("results", {}),
                        "success": True
                    })
                else:
                    all_results.append({
                        "file_index": file_index,
                        "file_name": file_context.get("file_name") or Path(file_context.get("file_path", "")).name,
                        "error": file_result.error_message,
                        "success": False
                    })
                    
            except Exception as e:
                self.logger.error(f"Error processing file {file_index}: {e}")
                all_results.append({
                    "file_index": file_index,
                    "file_name": file_context.get("file_name") or str(file_index),
                    "error": str(e),
                    "success": False
                })
        
        # After processing all files, handle blueprint generation if needed
        if "blueprint_gen" in [self.tool_key_mapping.get(tool, tool) for tool in tools] and accumulated_source_data_ids:
            try:
                blueprint_context = {
                    **context,
                    "source_data_ids": accumulated_source_data_ids,
                    "topic_name": topic_name
                }
                
                blueprint_input = self._prepare_tool_input("BlueprintGenerationTool", blueprint_context, {})
                blueprint_tool = TOOL_REGISTRY.get_tool("BlueprintGenerationTool")
                blueprint_result = blueprint_tool.execute_with_tracking(
                    blueprint_input, f"{execution_id}_blueprint"
                )
                
                if blueprint_result.success:
                    blueprint_id = blueprint_result.data.get("blueprint_id")
                    if blueprint_id:
                        # Update all file contexts with the blueprint ID
                        for result in all_results:
                            if result["success"]:
                                result["blueprint_id"] = blueprint_id
                        
                        # Process graph building for all files with the blueprint
                        if "graph_build" in [self.tool_key_mapping.get(tool, tool) for tool in tools]:
                            for file_result in all_results:
                                if file_result["success"]:
                                    source_data_id = file_result["results"].get("etl", {}).get("data", {}).get("source_data_id")
                                    if source_data_id and blueprint_id:
                                        try:
                                            graph_context = {
                                                **context,
                                                "source_data_id": source_data_id,
                                                "blueprint_id": blueprint_id,
                                                "topic_name": topic_name
                                            }
                                            
                                            graph_input = self._prepare_tool_input("GraphBuildTool", graph_context, {})
                                            graph_tool = TOOL_REGISTRY.get_tool("GraphBuildTool")
                                            graph_result = graph_tool.execute_with_tracking(
                                                graph_input, f"{execution_id}_graph_{file_result['file_index']}"
                                            )
                                            
                                            file_result["graph_result"] = graph_result.data
                                            
                                        except Exception as e:
                                            self.logger.error(f"Error building graph for file {file_result['file_index']}: {e}")
                                            file_result["graph_error"] = str(e)
            except Exception as e:
                self.logger.error(f"Error in batch blueprint generation: {e}")
        
        # Calculate overall statistics
        successful_files = sum(1 for r in all_results if r["success"])
        total_duration = (datetime.now(timezone.utc) - datetime.now(timezone.utc)).total_seconds()
        
        return ToolResult(
            success=successful_files > 0,
            data={
                "processed_files": all_results,
                "successful_count": successful_files,
                "total_count": total_files,
                "pipeline": tools,
                "accumulated_source_data_ids": accumulated_source_data_ids
            },
            execution_id=execution_id,
            duration_seconds=total_duration
        )
    
    def _execute_single_file_pipeline(self, tools: List[str], context: Dict[str, Any], execution_id: str) -> ToolResult:
        """
        Execute pipeline for a single file.
        
        Args:
            tools: List of tool names
            context: Context for single file
            execution_id: Execution ID
            
        Returns:
            ToolResult for single file processing
        """
        results = {}
        pipeline_context = context.copy()
        
        try:
            for tool_name in tools:
                tool = TOOL_REGISTRY.get_tool(tool_name)
                if not tool:
                    return ToolResult(
                        success=False,
                        error_message=f"Tool '{tool_name}' not found"
                    )
                
                # Prepare input for this tool
                tool_input = self._prepare_tool_input(tool_name, pipeline_context, results)
                
                # Execute tool
                result = tool.execute_with_tracking(tool_input, f"{execution_id}_{tool_name}")
                
                if not result.success:
                    return ToolResult(
                        success=False,
                        error_message=f"Tool '{tool_name}' failed: {result.error_message}",
                        execution_id=execution_id,
                        data={"failed_tool": tool_name, "previous_results": results}
                    )
                
                results[tool_name] = result
                pipeline_context = self._update_context(tool_name, pipeline_context, result)
            
            return ToolResult(
                success=True,
                data={"results": results},
                execution_id=execution_id
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error_message=str(e),
                execution_id=execution_id
            )
    
    def execute_scenario(self, scenario: str, context: Dict[str, Any], execution_id: Optional[str] = None) -> ToolResult:
        """
        Execute a specific scenario with appropriate pipeline.
        
        Args:
            scenario: One of 'single_doc_existing', 'batch_doc_existing', 'new_topic'
            context: Context data for the scenario
            execution_id: Optional execution ID
            
        Returns:
            ToolResult with scenario execution results
        """
        scenario_to_pipeline = {
            "single_doc_existing": "single_doc_existing_topic",
            "batch_doc_existing": "batch_doc_existing_topic", 
            "new_topic": "new_topic_batch"
        }
        
        if scenario not in scenario_to_pipeline:
            return ToolResult(
                success=False,
                error_message=f"Scenario '{scenario}' not supported"
            )
        
        return self.execute_pipeline(
            scenario_to_pipeline[scenario], 
            context, 
            execution_id
        )
    
    def execute_with_process_strategy(self, request_data: Dict[str, Any], execution_id: Optional[str] = None) -> ToolResult:
        """
        Execute pipeline based on process strategy parameter from API request.
        
        Args:
            request_data: API request data containing process_strategy
            execution_id: Optional execution ID
            
        Returns:
            ToolResult with execution results
        """
        execution_id = execution_id or str(uuid.uuid4())
        
        process_strategy = request_data.get("process_strategy", {})
        target_type = request_data.get("target_type", {})
        metadata = request_data.get("metadata", {})
        
        # Explicit pipeline execution
        if "pipeline" in process_strategy:
            pipeline = process_strategy["pipeline"]
            tools = [self.tool_key_mapping.get(tool_key, tool_key) for tool_key in pipeline]
            return self.execute_custom_pipeline(tools, request_data, execution_id)
        
        # Default pipeline selection
        topic_name = metadata.get("topic_name")
        file_count = len(request_data.get("files", []))
        is_new_topic = metadata.get("is_new_topic", False)
        
        # Determine input type and context
        input_type = "dialogue" if target_type == "personal_memory" else "document"
        if isinstance(request_data.get("input"), str) and not request_data.get("files"):
            input_type = "text"
        
        pipeline_name = self.select_default_pipeline(
            target_type, topic_name, file_count, is_new_topic, 
            input_type=input_type
        )
        return self.execute_pipeline(pipeline_name, request_data, execution_id)