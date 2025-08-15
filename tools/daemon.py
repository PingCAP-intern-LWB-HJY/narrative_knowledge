import logging
import time
import json
import uuid
import argparse
from collections import defaultdict
from typing import Dict, Any, Optional, Generator
from setting.db import SessionLocal
from knowledge_graph.models import RawDataSource, BackgroundTask
from tools.route_wrapper import ToolsRouteWrapper
from tools.api_integration import PipelineAPIIntegration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PipelineDaemon:
    """
    Daemon for managing pipeline execution.
    This class is responsible for orchestrating the execution of pipelines
    based on the provided configuration and context.
    """

    def __init__(self, check_interval: int = 60, mode: str = "files"):
        """
        Initialize the PipelineDaemon.

        Args:
            check_interval: Interval in seconds to check for new tasks
            mode: Processing mode - "files" for uploaded files or "memory" for memory chat batch
        """
        self.check_interval = check_interval
        self.mode = mode
        logger.info(
            f"PipelineDaemon initialized with check interval: {self.check_interval} seconds, mode: {mode}"
        )

    def start(self):
        """
        Start the PipelineDaemon.
        """
        self.is_running = True
        logger.info(f"PipelineDaemon started in {self.mode} mode")

        while self.is_running:
            try:
                if self.mode == "files":
                    result = self._process_uploaded_files()
                elif self.mode == "memory":
                    result = self._process_memory_chat_batch()
                else:
                    logger.error(f"Invalid mode: {self.mode}")
                    break
                
                if result:
                    logger.info(f"Processed result: {result}")
                    self.is_running = False  # Stop after processing
            except Exception as e:
                logger.error(f"Error in daemon main loop: {e}", exc_info=True)

            time.sleep(self.check_interval)

    def stop(self):
        """
        Stop the PipelineDaemon.
        """
        self.is_running = False
        logger.info("PipelineDaemon stopped")


    def register_background_task(self, task_id: str, task_type: str, topic_name: str, user_id: Optional[str] = None, message_count: int = 1) -> None:
        """Register a new background task for file/memory processing immediately."""
        with SessionLocal() as db:

            task = BackgroundTask(
                id=task_id,
                task_type=task_type,
                topic_name=topic_name,
                user_id=user_id,
                status="processing",
                message_count=message_count
            )
        db.add(task)
        db.commit()
        
    
    def _process_uploaded_files(self):
        """
        Process uploaded files in the pipeline.
        """
        logger.info("Processing uploaded files...")

        with SessionLocal() as db:
            uploaded_data_list = (
                db.query(RawDataSource)
                .filter(
                    RawDataSource.status == "uploaded",
                    RawDataSource.target_type == "knowledge_graph",
                )
                .all()
            )
            logger.info(
                f"Found {len(uploaded_data_list)} uploaded data sources to process"
            )

        grouped = defaultdict(list)

        for rds in uploaded_data_list:
            grouped[(rds.topic_name, rds.target_type, json.dumps(rds.process_strategy, sort_keys=True))].append(rds)

        logger.info(f"Grouped {len(uploaded_data_list)} uploaded files into {len(grouped)} groups for processing")

        for (topic_name, target_type, process_strategy_json), rds_list in grouped.items():

            process_strategy = json.loads(process_strategy_json) if process_strategy_json else None

            files = []
            for rds in rds_list:
                file_meta = {}
                link = None


                if rds.raw_data_source_metadata:
                    # 'link' is referenced as 'doc_link' in RawDataSource
                    custom_metadata = rds.raw_data_source_metadata.get("custom_metadata", {})
                    force_regenerate = custom_metadata.get("force_regenerate", False)
                    link = rds.raw_data_source_metadata.get("doc_link")  
                    content_type = rds.raw_data_source_metadata.get("content_type", None)
                    database_uri = rds.raw_data_source_metadata.get("database_uri", None)
                    force_regenerate = custom_metadata.get("force_regenerate", False)

                files.append({
                    "filename": rds.original_filename,
                    "metadata": file_meta,
                    "link": link,
                    "content_type": content_type
                })

            metadata = {
                "topic_name": topic_name,
                "force_regenerate": force_regenerate,
                "database_uri": database_uri
            }
            req_data = {
                "metadata": metadata,
                "target_type": target_type,
                "process_strategy": process_strategy,
                "force_regenerate": force_regenerate,
            }

            logger.info(f"Request data prepared for topic '{topic_name}' with {len(files)} files")
            execution_id = str(uuid.uuid4())
            try:
                self.register_background_task(
                    task_id=execution_id,
                    topic_name=topic_name,
                    task_type="file_processing",
                    message_count=len(files)
                )
                integration = PipelineAPIIntegration()
                # orchestrator = PipelineOrchestrator()
                result = integration.process_request(req_data, files, execution_id)
                logger.info(
                    f"Pipeline execution completed for topic '{topic_name}': {result}"
                )
                with SessionLocal() as db:
                    task = db.query(BackgroundTask).filter_by(id=execution_id).first()
                    if task:
                        task.status = "completed"
                        task.result = result.to_dict()
                        db.commit()
            except ValueError as e:
                logger.error(
                    f"Invalid process strategy for topic '{topic_name}': {e}",
                    exc_info=True
                )
                with SessionLocal() as db:
                    task = db.query(BackgroundTask).filter_by(id=execution_id).first()
                    if task:
                        task.status = "failed"
                        task.error_message = str(e)
                        db.commit()
                
                
            except Exception as e:
                logger.error(
                    f"Error executing pipeline for topic '{topic_name}': {e}",
                    exc_info=True
                )
        total_result = {
            "status": "success",
            "message": f"Processed {len(uploaded_data_list)} uploaded files across {len(grouped)} topics"
        }
        return  total_result       

    def _process_memory_chat_batch(self):
        """
        Process memory chat batch in the pipeline.
        """
        logger.info("Processing memory chat batch...")

        with SessionLocal() as db:
            uploaded_data_list = (
                db.query(RawDataSource)
                .filter(
                    RawDataSource.status == "uploaded",
                    RawDataSource.target_type == "personal_memory",
                )
                .all()
            )
            logger.info(
                f"Found {len(uploaded_data_list)} uploaded data sources to process"
            )

        grouped = defaultdict(list)

        for rds in uploaded_data_list:
            grouped[(rds.topic_name, rds.target_type, json.dumps(rds.process_strategy, sort_keys=True))].append(rds)

        logger.info(f"Grouped {len(uploaded_data_list)} memory messages into {len(grouped)} groups for processing")

        for (topic_name, target_type, process_strategy_json), rds_list in grouped.items():
            process_strategy = json.loads(process_strategy_json) if process_strategy_json else None
            
            messages = []
            for rds in rds_list:
                rds_metadata = rds.raw_data_source_metadata
                if rds_metadata:
                    # Extract messages from raw_data_source_metadata
                    metadata = rds.raw_data_source_metadata.get("metadata", {})
                    user_id = metadata.get("user_id")
                    if 'chat_messages' in rds_metadata:
                        messages.extend(rds_metadata['chat_messages'])
                build_id = rds.id
            
            execution_id = str(uuid.uuid4())
            try:
                self.register_background_task(
                    task_id=execution_id,
                    task_type="memory_processing",
                    topic_name=topic_name,
                    user_id=user_id,
                    message_count=len(messages)
                )

                # Prepare metadata with source_id for tools processing
                processing_metadata = {
                    "user_id": user_id,
                    "source_id": build_id,
                    "topic_name": topic_name
                }

                logger.info(f"Request data prepared for topic '{topic_name}' with {len(messages)} messages")

                # Process the existing source data
                tools_wrapper = ToolsRouteWrapper()
                result = tools_wrapper.process_json_request(
                    input_data=messages,
                    metadata=processing_metadata,
                    process_strategy=process_strategy,
                    target_type=target_type,
                )

                # Update task status with success and clean up chat_messages
                with SessionLocal() as db:
                    task = db.query(BackgroundTask).filter(BackgroundTask.id == execution_id).first()
                    if task:
                        task.status = "completed"
                        task.result = result.to_dict() if hasattr(result, 'to_dict') else result
                        db.commit()
                    
                    # Update RawDataSource to remove chat_messages from metadata and set status
                    for rds in rds_list:
                        rds_metadata = rds.raw_data_source_metadata
                        if rds_metadata and 'chat_messages' in rds_metadata:
                            # Remove chat_messages only and keep the rest
                            rds.raw_data_source_metadata = rds.raw_data_source_metadata.get("metadata", {})
                            rds.status = "etl_completed"
                            db.add(rds)
                    db.commit()
                
                logger.info(f"Background processing completed: {result.to_dict()}")
                
            except Exception as e:
                # Update task status with error
                with SessionLocal() as db:
                    task = db.query(BackgroundTask).filter(BackgroundTask.id == execution_id).first()
                    if task:
                        task.status = "failed"
                        task.error = str(e)
                        db.commit()
                logger.error(f"Background processing failed: {e}")
            
            except Exception as e:
                logger.error(
                    f"Error executing pipeline for topic '{topic_name}': {e}",
                    exc_info=True
                )

        total_result = {
            "status": "success",
            "message": f"Processed {len(uploaded_data_list)} uploaded inputs across {len(grouped)} topics"
        }
        return total_result

def main():
    """
    Main entry point for the PipelineDaemon.
    """
    parser = argparse.ArgumentParser(description='Pipeline Daemon for processing uploaded files or memory chat batches')
    parser.add_argument(
        '--mode',
        choices=['files', 'memory'],
        default='files',
        help='Processing mode: "files" for uploaded files or "memory" for memory chat batch (default: files)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Check interval in seconds (default: 5)'
    )
    
    args = parser.parse_args()
    
    daemon = PipelineDaemon(check_interval=args.interval, mode=args.mode)
    try:
        daemon.start()
    except KeyboardInterrupt:
        daemon.stop()
        logger.info("PipelineDaemon stopped by user")       

if __name__ == "__main__":
    main()