import logging
import time
import json
import hashlib
from collections import defaultdict
from typing import Dict, Any, Optional, Generator
from setting.db import SessionLocal
from knowledge_graph.models import RawDataSource, BackgroundTask
from tools.orchestrator import PipelineOrchestrator

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

    def __init__(self, check_interval: int = 10):
        """
        Initialize the PipelineDaemon.

        Args:
            check_interval: Interval in seconds to check for new tasks
        """
        self.check_interval = check_interval
        logger.info(
            f"PipelineDaemon initialized with check interval: {self.check_interval} seconds"
        )

    def start(self):
        """
        Start the PipelineDaemon.
        """
        self.is_running = True
        logger.info("PipelineDaemon started")

        while self.is_running:
            try:
                result = self._process_uploaded_files()
                if result:
                    logger.info(f"Processed files result: {result}")
                    # self.is_running = False  # Stop after processing files
            except Exception as e:
                logger.error(f"Error in daemon main loop: {e}", exc_info=True)

            time.sleep(self.check_interval)

    def stop(self):
        """
        Stop the PipelineDaemon.
        """
        self.is_running = False
        logger.info("PipelineDaemon stopped")


    def register_file_background_task(self,task_id: str, topic_name: str, file_count: int = 1) -> None:
        """Register a new background task for file processing immediately."""
        with SessionLocal() as db:

            task = BackgroundTask(
                task_id=task_id,
                task_type="file_processing",
                topic_name=topic_name,
                status="processing",
                message_count=file_count
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

            context = {
                "topic_name": topic_name,
                "target_type": target_type,
                "process_strategy": process_strategy,
                "files": []
            }

            for rds in rds_list:
                metadata = {"topic_name": rds.topic_name}
                link = None
                content_type = None

                if rds.raw_data_source_metadata:
                    link = rds.raw_data_source_metadata.get("doc_link")
                    content_type = rds.raw_data_source_metadata.get("content_type")

                context["files"].append({
                    "filename": rds.original_filename,
                    "metadata": metadata,
                    "link": link,
                    "content_type": content_type
                })
            logger.info(f"Context prepared for topic '{topic_name}': {len(context['files'])} files")
            execution_id = hashlib.sha256(topic_name.encode("utf-8")).hexdigest()
            logger.info(f"Execution ID for topic '{topic_name}': {execution_id}")
            try:
                self.register_file_background_task(
                    task_id=execution_id,
                    topic_name=topic_name,
                    file_count=len(context['files'])
                )
                
                orchestrator = PipelineOrchestrator()
                result = orchestrator.execute_with_process_strategy(context, execution_id)
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
def main():
    """
    Main entry point for the PipelineDaemon.
    """
    daemon = PipelineDaemon(check_interval=5)
    try:
        daemon.start()
    except KeyboardInterrupt:
        daemon.stop()
        logger.info("PipelineDaemon stopped by user")       
if __name__ == "__main__":
    main()