#!/bin/bash
# TiDB Cloud Documentation Upload Script
# Generated automatically based on content analysis

# Set the base path for documentation files
DOCS_PATH="${1:-/Users/hjy/Downloads/docs-master}"

echo "Using documentation path: $DOCS_PATH"


# Batch 1: Core Concepts
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-intro.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-quickstart.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-htap-quickstart.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/get-started-with-cli.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-poc.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/key-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/architecture-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/database-schema-concepts.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-intro.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-quickstart.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-htap-quickstart.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/get-started-with-cli.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-poc.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/key-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/architecture-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/database-schema-concepts.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_core_concepts", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# Batch 2: Development Guides
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/transaction-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/sql-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/ai-feature-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/data-service-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/scalability-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/serverless-high-availability.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/high-availability-with-multi-az.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/monitoring-concepts.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/transaction-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/sql-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/ai-feature-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/data-service-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/scalability-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/serverless-high-availability.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/high-availability-with-multi-az.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/monitoring-concepts.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_development_guides", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# Batch 3: Advanced Features
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/data-streaming-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/backup-and-restore-concepts.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/security-concepts.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-overview.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-build-cluster-in-cloud.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-tidb-crud-sql.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-choose-driver-or-orm.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-schema-design-overview.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-create-database.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-create-table.md" \
  -F "files=@$DOCS_PATH/develop/dev-guide-create-secondary-indexes.md" \
  -F "files=@$DOCS_PATH/vector-search/vector-search-overview.md" \
  -F "files=@$DOCS_PATH/vector-search/vector-search-get-started-using-sql.md" \
  -F "files=@$DOCS_PATH/vector-search/vector-search-get-started-using-python.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-migration-overview.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/create-tidb-cluster-serverless.md" \
  -F "files=@$DOCS_PATH/tidb-cloud/create-tidb-cluster.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/data-streaming-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/backup-and-restore-concepts.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/security-concepts.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-overview.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-build-cluster-in-cloud.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-tidb-crud-sql.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-choose-driver-or-orm.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-schema-design-overview.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-create-database.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-create-table.md", "https://github.com/pingcap/docs/blob/master/develop/dev-guide-create-secondary-indexes.md", "https://github.com/pingcap/docs/blob/master/vector-search/vector-search-overview.md", "https://github.com/pingcap/docs/blob/master/vector-search/vector-search-get-started-using-sql.md", "https://github.com/pingcap/docs/blob/master/vector-search/vector-search-get-started-using-python.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-migration-overview.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/create-tidb-cluster-serverless.md", "https://github.com/pingcap/docs/blob/master/tidb-cloud/create-tidb-cluster.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_advanced_features", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# Individual file uploads (for testing)

# TiDB Cloud Introduction
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-intro.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-intro.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_single_file", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# TiDB Cloud Quickstart
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-quickstart.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-quickstart.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_single_file", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# TiDB Cloud HTAP Quickstart
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-htap-quickstart.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-htap-quickstart.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_single_file", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# TiDB Cloud CLI
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/get-started-with-cli.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/get-started-with-cli.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_single_file", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# TiDB Cloud PoC
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@$DOCS_PATH/tidb-cloud/tidb-cloud-poc.md" \
  -F 'links=["https://github.com/pingcap/docs/blob/master/tidb-cloud/tidb-cloud-poc.md"]' \
  -F 'metadata={"topic_name": "tidb_cloud_single_file", "force_regenerate": "False"}' \
  -F "target_type=knowledge_graph"


# Usage:
# ./upload_tidb_docs.sh [docs_path]
# Example: ./upload_tidb_docs.sh /custom/path/to/docs
