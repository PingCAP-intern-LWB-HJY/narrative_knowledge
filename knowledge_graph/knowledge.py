from pathlib import Path
import logging
import hashlib
from typing import Dict, Any

from knowledge_graph.models import SourceData, GraphBuildStatus
from setting.db import SessionLocal
from etl.extract import extract_source_data

logger = logging.getLogger(__name__)


class KnowledgeBuilder:
    """
    A builder class for constructing knowledge graphs from documents.
    """

    def __init__(self):
        """
        Initialize the builder with a graph instance and specifications.
        """
        pass

    def extract_knowledge(self, source_path: str, attributes: Dict[str, Any], **kwargs):
        # Extract basic info of source
        doc_link = attributes.get("doc_link", None)
        if doc_link is None or doc_link == "":
            doc_link = source_path

        try:
            source_info = extract_source_data(source_path)
        except Exception as e:
            logger.error(f"Failed to process {source_path}: {e}")
            raise RuntimeError(f"Failed to process{source_path}: {e}")

        full_content = source_info.get("content", None)
        source_type = source_info.get("file_type", "document")

        name = Path(source_path).stem
        source_hash = hashlib.sha256(full_content.encode("utf-8")).hexdigest()

        with SessionLocal() as db:
            # Check if source data already exists by hash
            existing_source = (
                db.query(SourceData).filter(SourceData.hash == source_hash).first()
            )

            if existing_source:
                logger.info(
                    f"Source data already exists for {source_path}, id: {existing_source.id}"
                )

                return {
                    "status": "success",
                    "source_id": existing_source.id,
                    "source_type": existing_source.source_type,
                    "source_path": source_path,
                    "source_content": existing_source.content,
                    "source_link": existing_source.link,
                    "source_name": existing_source.name,
                }
            else:
                source_data = SourceData(
                    name=name,
                    content=full_content,
                    link=doc_link,
                    source_type=source_type,
                    hash=source_hash,
                    attributes=attributes,
                )

                db.add(source_data)
                db.commit()
                db.refresh(source_data)
                logger.info(
                    f"Source data created for {source_path}, id: {source_data.id}"
                )

                return {
                    "status": "success",
                    "source_id": source_data.id,
                    "source_path": source_path,
                    "source_content": source_data.content,
                    "source_link": source_data.link,
                    "source_name": source_data.name,
                    "source_type": source_type,
                }

    def create_build_status_record(self, source_id: str, topic_name: str) -> None:
        """
        Create a GraphBuildStatus record for the uploaded document.

        Args:
            source_id: The source document ID
            topic_name: The topic name for graph building

        Raises:
            Exception: If database operation fails
        """
        try:
            with SessionLocal() as db:
                # Check if record already exists
                existing_status = (
                    db.query(GraphBuildStatus)
                    .filter(
                        GraphBuildStatus.topic_name == topic_name,
                        GraphBuildStatus.source_id == source_id,
                    )
                    .first()
                )

                if not existing_status:
                    # Create new build status record
                    build_status = GraphBuildStatus(
                        topic_name=topic_name,
                        source_id=source_id,
                        status="pending",
                    )
                    db.add(build_status)
                    db.commit()
                    logger.info(
                        f"Created build status record for source {source_id} in topic {topic_name}"
                    )
                else:
                    logger.info(
                        f"Build status record already exists for source {source_id} in topic {topic_name}"
                    )

        except Exception as e:
            logger.error(f"Failed to create build status record: {e}")
            raise
