"""
Pipeline Orchestrator for dynamic tool sequencing.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import uuid

from tools.base import ToolResult
from tools.base import TOOL_REGISTRY
from setting.db import SessionLocal
from llm.factory import LLMInterface

# gloabl LLM client for default usage
llm_client = LLMInterface("openai", model="gpt-4o")


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

        # Auto-register tools
        self._register_tools()

        # Define standard pipelines using tool keys
        self.standard_pipelines = {
            # Knowledge graph pipelines
            "single_doc_existing_topic": ["etl", "graph_build"],
            "batch_doc_existing_topic": ["etl", "blueprint_gen", "graph_build"],
            "new_topic_batch": ["etl", "blueprint_gen", "graph_build"],
            "text_to_graph": ["graph_build"],
            # Memory pipelines
            "memory_direct_graph": [
                "memory_graph_build"
            ],  # Direct memory processing with graph building
            "memory_single": ["memory_graph_build"],  # Single memory processing
        }

        # Tool key to name mapping
        self.tool_key_mapping = {
            "etl": "DocumentETLTool",
            "blueprint_gen": "BlueprintGenerationTool",
            "graph_build": "GraphBuildTool",
            "memory_graph_build": "MemoryGraphBuildTool",
        }

    def _register_tools(self):
        """Auto-register all available tools."""
        try:
            # Import tools with absolute paths
            from .document_etl_tool import DocumentETLTool
            from .blueprint_generation_tool import BlueprintGenerationTool
            from .graph_build_tool import GraphBuildTool
            from .memory_graph_build_tool import MemoryGraphBuildTool

            # Register tools if not already registered
            if not TOOL_REGISTRY.get_tool("DocumentETLTool"):
                TOOL_REGISTRY.register(
                    DocumentETLTool(session_factory=self.session_factory)
                )
            if not TOOL_REGISTRY.get_tool("BlueprintGenerationTool"):
                TOOL_REGISTRY.register(
                    BlueprintGenerationTool(
                        session_factory=self.session_factory, llm_client=llm_client
                    )
                )
            if not TOOL_REGISTRY.get_tool("GraphBuildTool"):
                TOOL_REGISTRY.register(
                    GraphBuildTool(
                        session_factory=self.session_factory, llm_client=llm_client
                    )
                )
            if not TOOL_REGISTRY.get_tool("MemoryGraphBuildTool"):
                TOOL_REGISTRY.register(
                    MemoryGraphBuildTool(
                        session_factory=self.session_factory, llm_client=llm_client
                    )
                )

            self.logger.info("Tools registered successfully")

        except ImportError as e:
            self.logger.warning(f"Could not register all tools: {e}")
            import traceback

            self.logger.warning(f"Traceback: {traceback.format_exc()}")

    def execute_pipeline(
        self,
        pipeline_name: str,
        context: Dict[str, Any],
        execution_id: Optional[str] = None,
    ) -> ToolResult:
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
                success=False, error_message=f"Pipeline '{pipeline_name}' not found"
            )

        tool_keys = self.standard_pipelines[pipeline_name]
        tools = [self.tool_key_mapping[key] for key in tool_keys]

        self.logger.info(f"Execute pipeline with tools: {tools}")

        return self.execute_custom_pipeline(tools, context, execution_id)

    def execute_custom_pipeline(
        self,
        tools: List[str],
        context: Dict[str, Any],
        execution_id: Optional[str] = None,
    ) -> ToolResult:
        """
        Execute a custom pipeline with specific tool sequence.

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

        results = {}
        # 
        pipeline_context = context.copy()

        try:
            for tool_name in tools:
                tool = TOOL_REGISTRY.get_tool(tool_name)
                if not tool:
                    return ToolResult(
                        success=False, error_message=f"Tool '{tool_name}' not found"
                    )

                # Prepare input for this tool
                self.logger.info(f"Preparing input for tool: {tool_name}, context: {pipeline_context}")
                tool_input = self._prepare_tool_input(
                    tool_name, pipeline_context, results
                )

                # Validate input if tool has validate_input method
                if hasattr(tool, "validate_input"):
                    is_valid = tool.validate_input(tool_input)
                    if not is_valid:
                        return ToolResult(
                            success=False,
                            error_message=f"Tool '{tool_name}' failed: Input validation failed",
                            execution_id=execution_id,
                            data={"failed_tool": tool_name, "tool_input": tool_input},
                        )

                # Execute tool
                self.logger.info(f"Executing tool: {tool_name}")
                self.logger.info(f"Tool input: {tool_input}")
                result = tool.execute_with_tracking(
                    tool_input, f"{execution_id}_{tool_name}"
                )
                self.logger.info(f"{tool_name} result: {result.to_dict()}")
                if not result.success:
                    return ToolResult(
                        success=False,
                        error_message=f"Tool '{tool_name}' failed: {result.error_message}",
                        execution_id=execution_id,
                        data={"failed_tool": tool_name, "previous_results": results},
                    )

                results[tool_name] = result
                pipeline_context = self._update_context(
                    tool_name, pipeline_context, result
                )

                self.logger.info(f"Tool completed: {tool_name}")

            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            self.logger.info(
                f"Pipeline execution completed: {execution_id} in {duration:.2f}s"
            )

            self.logger.info(
                f"Preparing final ToolResult:{results}\nPipeline: {tools}\n"
            )

            return ToolResult(
                success=True,
                data={
                    "results": results,
                    "pipeline": tools,
                    "duration_seconds": duration,
                },
                execution_id=execution_id,
                duration_seconds=duration,
            )

        except Exception as e:
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            self.logger.error(f"Pipeline execution failed: {execution_id} - {e}")

            return ToolResult(
                success=False,
                error_message=str(e),
                execution_id=execution_id,
                duration_seconds=duration,
            )

    def select_default_pipeline(
        self,
        target_type: str,
        topic_name: str,
        file_count: int,
        is_new_topic: bool,
        input_type: str = "document",
        file_extension: str = "",
    ) -> str:
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
        self.logger.info(
            f"Process strategy not provided. Selecting appropriate default pipeline."
        )

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

    def _get_tool_key(self, tool_name: str) -> str:
        """Get tool key from tool name."""
        for key, name in self.tool_key_mapping.items():
            if name == tool_name:
                return key
        return tool_name

    def _prepare_tool_input(
        self,
        tool_name: str,
        context: Dict[str, Any],
        previous_results: Dict[str, ToolResult],
    ) -> Dict[str, Any]:
        """Prepare input for a specific tool based on context and previous results."""

        # Get tool key for consistent handling
        tool_key = self._get_tool_key(tool_name)

        if tool_key == "etl":
            files = context.get("files", [])
            request_metadata = context.get("metadata", {})
            if files:
                # Batch processing with files array - preserve request metadata
                return {
                    "files": files,
                    "topic_name": context.get("topic_name"),
                    "request_metadata": request_metadata,
                    "force_regenerate": context.get("force_regenerate", False),
                }
            else:
                # Single file processing
                return {
                    "file_path": context.get("file_path"),
                    "topic_name": context.get("topic_name"),
                    "metadata": request_metadata,
                    "force_regenerate": context.get("force_regenerate", False),
                    "link": context.get("link"),
                    "original_filename": context.get("original_filename"),
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
                }

            return {
                "topic_name": context.get("topic_name"),
                "source_data_ids": source_data_ids,
                "force_regenerate": context.get("force_regenerate", False),
            }

        elif tool_key == "graph_build":
            topic_name = context.get("topic_name")
            source_data_ids = context.get("source_data_ids", [])

            # Ensure we have source_data_ids
            if not source_data_ids and context.get("source_data_id"):
                source_data_ids = [context.get("source_data_id")]

            # Determine blueprint_id based on context
            blueprint_id = context.get("blueprint_id")

            # If no blueprint_id provided, check for existing one
            if not blueprint_id and topic_name:
                blueprint_id = self.get_existing_blueprint_id(topic_name)

            # Build input based on available data
            if source_data_ids and len(source_data_ids) == 1:
                # Single document processing
                input_data = {
                    "source_data_id": source_data_ids[0],
                    "force_regenerate": context.get("force_regenerate", False),
                }
                if blueprint_id:
                    input_data["blueprint_id"] = blueprint_id
                return input_data

            elif source_data_ids and blueprint_id:
                # Batch processing with specific blueprint
                return {
                    "source_data_ids": source_data_ids,
                    "blueprint_id": blueprint_id,
                    "force_regenerate": context.get("force_regenerate", False),
                }

            else:
                # Topic-based processing
                return {
                    "topic_name": topic_name,
                    "force_regenerate": context.get("force_regenerate", False),
                }

        elif tool_key == "memory_graph_build":
            # Memory processing requires chat_messages and user_id
            return {
                "chat_messages": context.get("chat_messages", []),
                "user_id": context.get("user_id"),
                "force_regenerate": context.get("force_regenerate", False),
                "source_id": context.get("source_id"),
            }

        return context.copy()

    def _update_context(
        self, tool_name: str, context: Dict[str, Any], result: ToolResult
    ) -> Dict[str, Any]:
        """Update context with results from a tool."""
        updated_context = context.copy()

        # Map tool name to key
        tool_key = None
        for key, name in self.tool_key_mapping.items():
            if name == tool_name:
                tool_key = key
                break

        if tool_key == "etl" and result.success:
            source_data_ids = result.data.get("source_data_ids", [])
            if source_data_ids:
                # Handle batch results
                if "source_data_ids" not in updated_context:
                    updated_context["source_data_ids"] = []
                updated_context["source_data_ids"].extend(source_data_ids)

                # For single file compatibility, use the first ID
                if len(source_data_ids) == 1:
                    updated_context["source_data_id"] = source_data_ids[0]

            updated_context["topic_name"] = result.metadata.get("topic_name")

        elif tool_key == "blueprint_gen" and result.success:
            updated_context["blueprint_id"] = result.data.get("blueprint_id")
            updated_context["topic_name"] = result.metadata.get("topic_name")
            self.logger.info(f"successfully updated context: 'blueprint_id:{updated_context['blueprint_id']}, topic_name:{updated_context['topic_name']}' after blueprint generation")
        return updated_context

    def get_existing_blueprint_id(self, topic_name: str) -> Optional[str]:
        """
        Look up the latest ready blueprint for a topic.

        Args:
            topic_name: Name of the topic

        Returns:
            Blueprint ID if found, None otherwise
        """
        from knowledge_graph.models import AnalysisBlueprint

        self.logger.info(
            f"Looking up for the latest ready blueprint for topic: {topic_name}"
        )
        with self.session_factory() as db:
            blueprint = (
                db.query(AnalysisBlueprint)
                .filter(
                    AnalysisBlueprint.topic_name == topic_name,
                    AnalysisBlueprint.status == "ready",
                )
                .order_by(AnalysisBlueprint.created_at.desc())
                .first()
            )

            return blueprint.id if blueprint else None

    def execute_with_process_strategy(
        self, context: Dict[str, Any], execution_id: Optional[str] = None
    ) -> ToolResult:
        """
        Execute pipeline based on process strategy parameter from API request.

        Args:
            context: API request data containing process_strategy
            execution_id: Optional execution ID

        Returns:
            ToolResult with execution results
        """
        execution_id = execution_id or str(uuid.uuid4())

        process_strategy = context.get("process_strategy", {})
        target_type = context.get("target_type", {})
        metadata = context.get("metadata", {})

        # Explicit pipeline execution
        if "pipeline" in process_strategy:
            if "knowledge_graph" in target_type:
                pipeline = process_strategy["pipeline"]
                self.logger.info(
                    f"We have process_strategy, with target_type '{target_type}' and specific pipelines: {pipeline}"
                )
                try:
                    tools = [self.tool_key_mapping[key] for key in pipeline]
                except KeyError as e:
                    return ToolResult(
                        success=False,
                        error_message=f"Invalid tool key {e} in pipeline configuration",
                    )
                return self.execute_custom_pipeline(tools, context, execution_id)
            elif "personal_memory" in target_type:
                tools = ["MemoryGraphBuildTool"]
                # Tell the user we still use MemoryGraphBuildTool even though process_strategy is provided
                self.logger.info(
                    f"We have process_strategy with target_type '{target_type}'. Using tool '{tools}'"
                )
                return self.execute_custom_pipeline(tools, context, execution_id)

        # Default pipeline selection
        topic_name = metadata.get("topic_name")
        file_count = len(context.get("files", []))
        is_new_topic = context.get("is_new_topic", False)

        # Determine input type and context
        input_type = "dialogue" if target_type == "personal_memory" else "document"
        if isinstance(context.get("input"), str) and not context.get("files"):
            input_type = "text"

        self.logger.info(f"Input type is: {input_type}")
        pipeline_name = self.select_default_pipeline(
            target_type, topic_name, file_count, is_new_topic, input_type=input_type
        )

        self.logger.info(f"Using pipeline name: {pipeline_name}")

        return self.execute_pipeline(pipeline_name, context, execution_id)
