"""
Background daemon for processing pending graph build tasks.
"""

import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from setting.db import SessionLocal
from knowledge_graph.models import GraphBuildStatus, SourceData
from knowledge_graph.graph_builder import KnowledgeGraphBuilder
from llm.factory import LLMInterface
from llm.embedding import get_text_embedding

logger = logging.getLogger(__name__)


class GraphBuildDaemon:
    """
    Background daemon for processing pending graph build tasks.
    """

    def __init__(
        self,
        llm_client: Optional[LLMInterface] = None,
        embedding_func=None,
        check_interval: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize the graph build daemon.

        Args:
            llm_client: LLM interface for processing
            embedding_func: Function to generate embeddings
            check_interval: Interval in seconds to check for pending tasks
            max_retries: Maximum number of retries for failed tasks
        """
        self.llm_client = llm_client or LLMInterface("openai_like", "qwen3-32b")
        self.embedding_func = embedding_func or get_text_embedding
        self.check_interval = check_interval
        self.max_retries = max_retries
        self.graph_builder = KnowledgeGraphBuilder(self.llm_client, self.embedding_func)
        self.is_running = False

    def start(self):
        """Start the daemon."""
        self.is_running = True
        logger.info("Graph build daemon started")

        while self.is_running:
            try:
                self._process_pending_tasks()
            except Exception as e:
                logger.error(f"Error in daemon main loop: {e}", exc_info=True)

            time.sleep(self.check_interval)

    def stop(self):
        """Stop the daemon."""
        self.is_running = False
        logger.info("Graph build daemon stopped")

    def _process_pending_tasks(self):
        """Process the earliest pending graph build topic."""
        # Step 1: Find earliest topic and prepare data (inside db session)
        topic_name, source_ids, topic_docs = self._prepare_topic_build()

        if not topic_name:
            return

        logger.info(
            f"Processing earliest topic: {topic_name} with {len(source_ids)} sources"
        )

        try:
            # Step 2: Build knowledge graph (outside db session)
            logger.info(f"Starting graph build for topic: {topic_name}")
            result = self.graph_builder.build_knowledge_graph(topic_name, topic_docs)

            # Step 3: Update final status (new db session)
            self._update_final_status(topic_name, source_ids, "completed")

            logger.info(f"Successfully completed graph build for topic: {topic_name}")
            logger.info(f"Build results: {result}")

        except Exception as e:
            error_message = f"Graph build failed: {str(e)}"
            logger.error(
                f"Failed to build graph for topic {topic_name}: {e}", exc_info=True
            )

            # Update tasks to failed status
            self._update_final_status(topic_name, source_ids, "failed", error_message)

    def _prepare_topic_build(self) -> Tuple[Optional[str], List[str], List[Dict]]:
        """
        Prepare topic build by finding earliest topic, updating status, and getting source data.

        Returns:
            Tuple of (topic_name, source_ids, topic_docs) or (None, [], []) if no pending tasks
        """
        with SessionLocal() as db:
            # Find the earliest pending topic
            earliest_topic = self._get_earliest_pending_topic(db)

            if not earliest_topic:
                return None, [], []

            # Get all pending tasks for this topic
            topic_tasks = self._get_pending_tasks_for_topic(db, earliest_topic)
            source_ids = [task.source_id for task in topic_tasks]

            # Update all tasks to processing status
            self._update_task_status(db, earliest_topic, source_ids, "processing")

            # Fetch source data and create source list
            topic_docs = self._create_source_list(db, source_ids)

            if not topic_docs:
                logger.warning(f"No valid sources found for topic: {earliest_topic}")
                self._update_task_status(
                    db, earliest_topic, source_ids, "failed", "No valid sources found"
                )
                return None, [], []

            return earliest_topic, source_ids, topic_docs

    def _get_earliest_pending_topic(self, db: Session) -> Optional[str]:
        """
        Get the topic name with the earliest scheduled_at time among pending tasks.

        Args:
            db: Database session

        Returns:
            Topic name of the earliest pending task, or None if no pending tasks
        """
        earliest_task = (
            db.query(GraphBuildStatus)
            .filter(
                or_(
                    GraphBuildStatus.status == "pending",
                    GraphBuildStatus.status == "processing",
                )
            )
            .order_by(GraphBuildStatus.scheduled_at.asc())
            .first()
        )

        return earliest_task.topic_name if earliest_task else None

    def _get_pending_tasks_for_topic(
        self, db: Session, topic_name: str
    ) -> List[GraphBuildStatus]:
        """
        Get all pending tasks for a specific topic.

        Args:
            db: Database session
            topic_name: Name of the topic

        Returns:
            List of pending GraphBuildStatus records for the topic
        """
        return (
            db.query(GraphBuildStatus)
            .filter(
                and_(
                    or_(
                        GraphBuildStatus.status == "pending",
                        GraphBuildStatus.status == "processing",
                    ),
                    GraphBuildStatus.topic_name == topic_name,
                )
            )
            .order_by(GraphBuildStatus.scheduled_at.asc())
            .all()
        )

    def _update_task_status(
        self,
        db: Session,
        topic_name: str,
        source_ids: List[str],
        status: str,
        error_message: Optional[str] = None,
    ):
        """
        Update the status of graph build tasks.

        Args:
            db: Database session
            topic_name: Name of the topic
            source_ids: List of source IDs to update
            status: New status to set
            error_message: Error message if status is 'failed'
        """
        try:
            update_data = {"status": status, "updated_at": func.current_timestamp()}

            if error_message:
                update_data["error_message"] = error_message

            db.query(GraphBuildStatus).filter(
                and_(
                    GraphBuildStatus.topic_name == topic_name,
                    GraphBuildStatus.source_id.in_(source_ids),
                )
            ).update(update_data, synchronize_session=False)

            db.commit()
            logger.info(f"Updated {len(source_ids)} tasks to status: {status}")

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update task status: {e}", exc_info=True)
            raise

    def _update_final_status(
        self,
        topic_name: str,
        source_ids: List[str],
        status: str,
        error_message: Optional[str] = None,
    ):
        """
        Update the final status of graph build tasks using a new database session.
        This is used after the long-running build_knowledge_graph operation.

        Args:
            topic_name: Name of the topic
            source_ids: List of source IDs to update
            status: New status to set
            error_message: Error message if status is 'failed'
        """
        try:
            with SessionLocal() as db:
                update_data = {"status": status, "updated_at": func.current_timestamp()}

                if error_message:
                    update_data["error_message"] = error_message

                db.query(GraphBuildStatus).filter(
                    and_(
                        GraphBuildStatus.topic_name == topic_name,
                        GraphBuildStatus.source_id.in_(source_ids),
                    )
                ).update(update_data, synchronize_session=False)

                db.commit()
                logger.info(
                    f"Updated {len(source_ids)} tasks to final status: {status}"
                )

        except Exception as e:
            logger.error(f"Failed to update final task status: {e}", exc_info=True)
            # Don't raise here as the graph building itself might have succeeded

    def _create_source_list(self, db: Session, source_ids: List[str]) -> List[Dict]:
        """
        Create a list of source documents for graph building.

        Args:
            db: Database session
            source_ids: List of source IDs to fetch

        Returns:
            List of source document dictionaries
        """
        sources = db.query(SourceData).filter(SourceData.id.in_(source_ids)).all()

        topic_docs = []
        for source in sources:
            if source.content:  # Only include sources with content
                topic_docs.append(
                    {
                        "source_id": source.id,
                        "source_name": source.name,
                        "source_content": source.content,
                        "source_link": source.link,
                    }
                )
            else:
                logger.warning(
                    f"Source {source.id} ({source.name}) has no content, skipping"
                )

        return topic_docs

    def get_daemon_status(self) -> Dict:
        """
        Get current daemon status and statistics.

        Returns:
            Dictionary with daemon status information
        """
        with SessionLocal() as db:
            pending_count = (
                db.query(GraphBuildStatus)
                .filter(GraphBuildStatus.status == "pending")
                .count()
            )

            processing_count = (
                db.query(GraphBuildStatus)
                .filter(GraphBuildStatus.status == "processing")
                .count()
            )

            completed_count = (
                db.query(GraphBuildStatus)
                .filter(GraphBuildStatus.status == "completed")
                .count()
            )

            failed_count = (
                db.query(GraphBuildStatus)
                .filter(GraphBuildStatus.status == "failed")
                .count()
            )

        return {
            "is_running": self.is_running,
            "check_interval": self.check_interval,
            "pending_tasks": pending_count,
            "processing_tasks": processing_count,
            "completed_tasks": completed_count,
            "failed_tasks": failed_count,
            "total_tasks": pending_count
            + processing_count
            + completed_count
            + failed_count,
        }
