# Narrative Knowledge API

This module provides a REST API for the Narrative Knowledge system, enabling document upload, processing, and querying for knowledge graph building.

## Quick Start

### 1. Install Dependencies

```bash
poetry install
```

### 2. Start the API Server
#### You can start the API using either method:
##### Method 1: Run the main module directly
```bash
poetry run python -m api.main
```
##### Method 2: Use uvicorn (recommended for production)
```bash
poetry run uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 2
```

The API will be available at `http://localhost:8000`

### 3. View API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Upload Documents

**POST** `/api/v1/knowledge/upload`

Upload and process documents for knowledge graph building with batch support.

**Parameters:**
- `files`: One or more files (PDF, Markdown, TXT, SQL)
- `links`: List of links to original documents (must match number of files)
  - Recommended to use accessible links
  - If not available, you can use custom unique addresses
  - Must ensure uniqueness
- `topic_name`: Topic name for knowledge graph building (required)
- `database_uri`: Database connection string (optional, uses local if not provided)

**Example using curl (single file):**

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/upload" \
  -F "files=@document.pdf" \
  -F "links=https://docs.google.com/document/d/abc123" \
  -F "topic_name=project-alpha"
```

**Example using curl (batch upload):**

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/upload" \
  -F "files=@document1.pdf" \
  -F "files=@document2.md" \
  -F "links=https://docs.google.com/document/d/abc123" \
  -F "links=https://github.com/repo/readme" \
  -F "topic_name=project-alpha"
```

**Response:**
```json
{
  "status": "success",
  "message": "Batch upload completed: 2/2 documents processed successfully",
  "data": {
    "uploaded_count": 2,
    "total_count": 2,
    "success_rate": 1.0,
    "documents": [
      {
        "id": "cc5b92b6-ef73-4c4d-8b54-60c610d3443d",
        "name": "document1",
        "file_path": "uploads/project-alpha/document1/document1.pdf",
        "doc_link": "https://docs.google.com/document/d/abc123",
        "file_type": "pdf",
        "status": "processed"
      },
      {
        "id": "dd6c03c7-fg84-5d5e-9c65-71d721e4554e",
        "name": "document2",
        "file_path": "uploads/project-alpha/document2/document2.md",
        "doc_link": "https://github.com/repo/readme",
        "file_type": "markdown",
        "status": "processed"
      }
    ],
    "failed": []
  }
}
```

### Trigger Document Processing

**POST** `/api/v1/knowledge/trigger-processing`

Manually trigger processing for documents in a specific topic.

**Parameters:**
- `topic_name`: Name of the topic to trigger processing for (required)
- `database_uri`: Database URI to filter tasks (optional)

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/trigger-processing" \
  -F "topic_name=project-alpha"
```

**Response:**
```json
{
  "status": "success",
  "message": "Processing triggered for topic: project-alpha",
  "data": {
    "topic_name": "project-alpha",
    "triggered_count": 2,
    "total_documents": 2
  }
}
```

### List Topics

**GET** `/api/v1/knowledge/topics`

Retrieve a list of all topics with their processing status summary.

**Query Parameters:**
- `database_uri`: Filter topics by database URI (optional)
  - Empty string or not provided: Local database topics
  - Specific URI: External database topics

**Example:**
```bash
curl "http://localhost:8000/api/v1/knowledge/topics"
```

**Example with database filter:**
```bash
curl "http://localhost:8000/api/v1/knowledge/topics?database_uri=postgresql://user:pass@host:5432/db"
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "topics": [
      {
        "topic_name": "project-alpha",
        "total_documents": 5,
        "uploaded_count": 5,
        "pending_count": 1,
        "processing_count": 0,
        "completed_count": 3,
        "failed_count": 1,
        "latest_update": "2024-01-15T10:35:00",
        "database_uri": ""
      },
      {
        "topic_name": "project-beta",
        "total_documents": 3,
        "uploaded_count": 3,
        "pending_count": 0,
        "processing_count": 1,
        "completed_count": 2,
        "failed_count": 0,
        "latest_update": "2024-01-15T11:20:00",
        "database_uri": "postgresql://user:pass@host:5432/external_db"
      }
    ],
    "total_topics": 2,
    "filter_database_uri": null,
    "source": "local_database"
  }
}
```

## Configuration

### Supported File Types
- PDF (`.pdf`) → document
- Markdown (`.md`) → document  
- Text (`.txt`) → document
- SQL (`.sql`) → code

### File Size Limits
- Maximum total file size for batch upload: 30MB
- Individual file size limit: 30MB

### Document Storage
Documents are stored in a versioned directory structure:
- Base path: `uploads/<topic_name>/<filename>/`
- Each document directory contains:
  - The original file
  - `document_metadata.json` with document information
- If a document with the same metadata exists, it will reuse the existing directory
- If a document with different metadata exists, a new versioned directory will be created (e.g., `filename_v2/`)

## Error Handling

The API uses standardized error responses for all endpoints:

**HTTP Error Response:**
```json
{
  "error": {
    "code": "HTTP_ERROR",
    "message": "Error message here",
    "status_code": 400
  }
}
```

**Internal Error Response:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred"
  }
}
```

## Enhanced Data Processing Pipeline

**POST** `/api/v1/save`

Enhanced endpoint for saving and processing data using the tools pipeline system. Supports both file uploads and JSON input with configurable processing strategies and detailed execution tracking.

**Content-Type Support:**
- `multipart/form-data`: For file uploads
- `application/json`: For JSON data input

### For File Uploads (`multipart/form-data`):

#### Method 1: Separate `links` Parameter (single string or array)
**Parameters:**
- `files`: Single/Batch file(s) to be uploaded (required)
- `links`: Original document link (optional, must match the number of files, single string or array)
- `metadata`: JSON string containing processing metadata (required)
  - `topic_name`: Topic name for knowledge graph building (required)
  - `force_regenerate`: [Boolean] Whether to force regeneration if data already been processed (optional)
  - Additional custom metadata fields
- `target_type`: Processing target type (required, e.g., "knowledge_graph")
- `process_strategy`: JSON string with processing pipeline configuration (optional)
  - `pipeline`: Array of tool names to execute in sequence
  - Example: `{"pipeline": ["etl", "blueprint_gen", "graph_build"]}`

**Examples using curl:**
Single File Uploading:

```bash
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@pipeline_design.md" \
  -F 'links="https://docs.com/doc1"' \
  -F 'metadata={"topic_name":"single0","force_regenerate":"True"}' \
  -F "target_type=knowledge_graph" \
  -F 'process_strategy={"pipeline":["etl","blueprint_gen","graph_build"]}'
```

Batch Files Uploading: 

```bash
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@pipeline_design.md" \
  -F "files=@SmartSave_api_v1.md" \
  -F "files=@knowledge_graph_quality_standard.md" \
  -F 'links=["https://docs.com/doc1", "https://docs.com/doc2", "https://test.com/files"]' \
  -F 'metadata={"topic_name":"batch_t1","force_regenerate":"False"}' \
  -F "target_type=knowledge_graph" \
  -F 'process_strategy={"pipeline":["etl","blueprint_gen","graph_build"]}'
```

#### Alternative Method to include `links`
##### Include `links` directly in metadata (single string or array)

**Parameters:**
- `files`: Single/Batch files to be uploaded (required)
- `metadata`: JSON string containing processing metadata (required)
  - `topic_name`: Topic name for knowledge graph building (required)
  - `links`: Original document links (optional, single string or array)
  - `force_regenerate`: [Boolean] Force regeneration if data already been processed (optional)
  - Additional custom metadata fields
- `target_type`: Processing target type (required, e.g., "knowledge_graph")
- `process_strategy`: JSON string with processing pipeline configuration (optional)
  - `pipeline`: Array of tool names to execute in sequence
  - Example: `{"pipeline": ["etl", "blueprint_gen", "graph_build"]}`

**Examples using curl:**
Single File uploading:

```bash
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@pipeline_design.md" \
  -F 'metadata={"topic_name":"single0","links":"https://example.com/doc"}' \
  -F "target_type=knowledge_graph" \
  -F 'process_strategy={"pipeline":["etl","blueprint_gen","graph_build"]}'
```

Batch Files Uploading:

```bash
curl -X POST "http://localhost:8000/api/v1/save" \
  -F "files=@pipeline_design.md" \
  -F "files=@SmartSave_api_v1.md" \
  -F "files=@knowledge_graph_quality_standard.md" \
  -F 'metadata={"topic_name":"batch_t1","links":["https://example.com/doc","https://docs.com/doc2", "https://test.com/files"]}' \
  -F "target_type=knowledge_graph" \
  -F 'process_strategy={"pipeline":["etl","blueprint_gen","graph_build"]}'
```

**Response (For Single File Uploading):**
```json
{
  "success": true,
  "data": {
    "results": {
      "DocumentETLTool": {
        "success": true,
        "data": {
          "source_data_ids": ["214328f2-b13a-4483-aebe-f93994cc5ec8"],
          "batch_summary": {
            "total_files": 1,
            "processed_files": 1,
            "reused_files": 0,
            "failed_files": 0
          }
        },
        "execution_id": "f1ed254e-0ee8-44d3-bc53-d8b13d176d51_DocumentETLTool",
        "duration_seconds": 1.35
      },
      "BlueprintGenerationTool": {
        "success": true,
        "data": {
          "blueprint_id": "098409c3-732d-48ba-92e3-f475ecceadae",
          "reused_existing": true,
          "contributing_source_data_count": 1
        },
        "execution_id": "f1ed254e-0ee8-44d3-bc53-d8b13d176d51_BlueprintGenerationTool",
        "duration_seconds": 0.33
      },
      "GraphBuildTool": {
        "success": true,
        "data": {
          "triplets_extracted": 3,
          "entities_created": 0,
          "relationships_created": 1
        },
        "execution_id": "f1ed254e-0ee8-44d3-bc53-d8b13d176d51_GraphBuildTool",
        "duration_seconds": 18.70
      }
    },
    "pipeline": ["DocumentETLTool", "BlueprintGenerationTool", "GraphBuildTool"],
    "duration_seconds": 20.39
  },
  "error_message": null,
  "execution_id": "f1ed254e-0ee8-44d3-bc53-d8b13d176d51",
  "duration_seconds": 20.39
}
```



**Response (For Batch Files Uploading):**
```json
{
  "success": true,
  "data": {
    "results": {
      "DocumentETLTool": {
        "success": true, 
        "data": {
          "source_data_ids": ["505f936e-d130-442b-95d5-f71677912208","0ac2d49c-d7ea-43fc-8304-3146ab38227d","a4af367d-b141-4c3e-a525-75d27f8a296c"],
          "results": [{
            "source_data_id": "505f936e-d130-442b-95d5-f71677912208",
            "content_hash": "8a8a18f81dc598d0d70aa645e24957cad56aaeda01f5ab9eddd46ff6ca847795",
            "content_size": 8184,
            "source_type": "text/markdown",
            "reused_existing": true,
            "status": "success",
            "file_path": "/var/folders/1l/ncvsdgnj74b127ww1sc4d0t00000gn/T/tmpi6k628u5/0_pipeline_design.md"
          },
            {
            "source_data_id": "0ac2d49c-d7ea-43fc-8304-3146ab38227d",
            "content_hash": "742c13197253c16bcc5fdec6fa7048c2492f4cf6946714d9fbc26a7df948e1ad",
            "content_size": 4106,
            "source_type": "text/markdown",
            "reused_existing": true,
            "status": "success",
            "file_path": "/var/folders/1l/ncvsdgnj74b127ww1sc4d0t00000gn/T/tmpi6k628u5/1_SmartSave_api_v1.md"
          },
            {
            "source_data_id": "a4af367d-b141-4c3e-a525-75d27f8a296c",
            "content_hash": "4c7d00f36c2f0dddad20cf5e6e36a7176d820c2ffefe35ece545775995e2a9b8",
            "content_size": 8841,
            "source_type": "text/markdown",
            "reused_existing": false,
            "status": "success",
            "file_path": "/var/folders/1l/ncvsdgnj74b127ww1sc4d0t00000gn/T/tmpi6k628u5/2_knowledge_graph_quality_standard.md"
          }],
          "batch_summary": {
            "total_files": 3,
            "processed_files": 1,
            "reused_files": 2,
            "failed_files": 0
          }
        },
        "error_message": null,
        "metadata": {
          "topic_name": "batch_t1",
          "total_files": 3
        },
        "execution_id": "1f12e7df-ef01-4037-9268-7688298dbfb0_DocumentETLTool",
        "duration_seconds": 5.791588,
        "timestamp": "2025-08-04T21:10:42.725552+00:00"
      },
      "BlueprintGenerationTool": {
        "success": true,
        "data": {
          "blueprint_id": "cc039049-0584-4cee-a3f6-0736d8b45056",
          "reused_existing": false,
          "contributing_source_data_count": 3,
          "source_data_version_hash": "59e4c02cbd094d25e50ec216c983a909aa89bcd4421e2555c1d4b6483bf76b46",
          "blueprint_summary": {
            "canonical_entities_count": 3,
            "key_patterns_count": 3,
            "global_timeline_events": 2,
            "processing_instructions_length": 632,
            "cognitive_maps_used": 3
          }
        },
        "error_message": null,
        "metadata": {
          "topic_name": "batch_t1",
          "source_data_count": 3,
          "cognitive_maps_count": 3
        },
        "execution_id": "1f12e7df-ef01-4037-9268-7688298dbfb0_BlueprintGenerationTool",
        "duration_seconds": 29.842363,
        "timestamp": "2025-08-04T21:11:12.568225+00:00"
      },
      "GraphBuildTool": {
        "success": true,
        "data": {
          "blueprint_id": "cc039049-0584-4cee-a3f6-0736d8b45056",
          "processed_count": 1,
          "failed_count": 0,
          "total_entities_created": 2,
          "total_relationships_created": 1,
          "total_triplets_extracted": 1,
          "results": [{
            "source_data_id": "a4af367d-b141-4c3e-a525-75d27f8a296c",
            "status": "success",
            "entities_created": 2,
            "relationships_created": 1,
            "triplets_extracted": 1
          }]
        },
        "error_message": null,
        "metadata": {
          "blueprint_id":"cc039049-0584-4cee-a3f6-0736d8b45056",
          "source_data_count": 3
        },
        "execution_id": "1f12e7df-ef01-4037-9268-7688298dbfb0_GraphBuildTool",
        "duration_seconds": 20.814152,
        "timestamp": "2025-08-04T21:11:33.024326+00:00"
      }
    },
    "pipeline": ["DocumentETLTool","BlueprintGenerationTool","GraphBuildTool"],
    "duration_seconds": 56.450806
  },
  "error_message": null,
  "metadata": {},
  "execution_id": "1f12e7df-ef01-4037-9268-7688298dbfb0",
  "duration_seconds": 56.450806,
  "timestamp": "2025-08-04T21:11:33.384224+00:00"
}
```

### For JSON Input (`application/json`):

**Parameters:**
- `input`: The raw data to process - can be chat history array or any JSON data (required)
- `metadata`: JSON object with processing context (required)
  - `user_id`: User identifier for personal memory processing (required)
  - Additional context fields as needed
- `target_type`: Processing target type (required, e.g., "personal_memory")
- `process_strategy`: JSON object with processing pipeline configuration (optional)
  - `pipeline`: Array of tool names to execute
  - For JSON input, use `["blueprint_gen", "graph_build"]` (ETL not needed)
  - For memory processing, now use default pipeline (MemoryGraphBuild), regardless of `process_strategy`

**Example using curl (chat history):**
```bash
curl -X POST "http://localhost:8000/api/v1/save" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      {
        "role": "user", 
        "content": "How do I set up SSH keys for GitHub?"
      },
      {
        "role": "assistant", 
        "content": "To set up SSH keys for GitHub..."
      }
    ],
    "metadata": {
      "user_id": "user123",
      "session_id": "session_456"
    },
    "target_type": "personal_memory",
    "process_strategy": {
      "pipeline": ["blueprint_gen", "graph_build"]
    }
  }'
```

**Example using curl (raw JSON data) (Not supported yet):**
```bash
curl -X POST "http://localhost:8000/api/v1/save" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "notes": "Meeting notes from project planning",
      "participants": ["Alice", "Bob", "Charlie"],
      "action_items": [
        "Set up development environment",
        "Create project timeline",
        "Assign team roles"
      ]
    },
    "metadata": {
      "user_id": "user789",
      "source": "meeting_notes"
    },
    "target_type": "personal_memory",
    "process_strategy": {
      "pipeline": ["blueprint_gen", "graph_build"]
    }
  }'
```

**Response (For memory processing):**
```json
{
  "success": true,
  "message": "Processing completed successfully",
  "data": {
    "results": {
      "MemoryGraphBuildTool": { 
        "success": true,
        "data": {
          "user_id": "user123",
          "topic_name": "The personal information of user123",
          "source_data_id": "6f719586-a5d5-4fa3-9747-32af7ebc48b6",
          "knowledge_block_id": "5245b45e-5784-4f97-9761-8d55d91521b7",
          "entities_created": 0,
          "relationships_created": 1,
          "triplets_extracted": 1,
          "status": "completed"
        },
        "error_message": null,
        "metadata": {
          "user_id": "user123",
          "message_count": 2,
          "topic_name": "The personal information of user123"
        },
        "execution_id": "dea4dcb1-9325-492e-8dec-d9afd9a0046d_MemoryGraphBuildTool",
        "duration_seconds": 32.593251,
        "timestamp": "2025-08-01T22:55:24.658312+00:00"
      }
    },
    "pipeline": ["MemoryGraphBuildTool"],
    "duration_seconds": 32.593757
  },
  "execution_id": "dea4dcb1-9325-492e-8dec-d9afd9a0046d"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "results": {
      "BlueprintGenerationTool": {
        "success": true,
        "data": {
          "blueprint_id": "def456ghi-789-012-345-6789abcdef01",
          "reused_existing": false,
          "contributing_source_data_count": 1,
          "source_data_version_hash": "a1b2c3d4e5f6789012345678901234567890abcd"
        },
        "execution_id": "exec_123456_json_BlueprintGenerationTool",
        "duration_seconds": 1.42
      },
      "GraphBuildTool": {
        "success": true,
        "data": {
          "triplets_extracted": 5,
          "entities_created": 3,
          "relationships_created": 2
        },
        "execution_id": "exec_123456_json_GraphBuildTool",
        "duration_seconds": 12.15
      }
    },
    "pipeline": ["BlueprintGenerationTool", "GraphBuildTool"],
    "duration_seconds": 14.42
  },
  "error_message": null,
  "execution_id": "exec_123456_json",
  "duration_seconds": 14.42
}
```

### Relavant Settings for testing
- **LLM Client**: Currently use default `llm_client` as `openai` with model `gpt-4o`
- **Embedding Function**: Currently use default `embedding_model` as `hf.co/Qwen/Qwen3-Embedding-8B-GGUF:Q8_0` with base_url `http://localhost:11434/v1/`
- Export environment variables `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_MODEL_API_KEY`, `DATABASE_URI` before testing.


### Available Pipeline Tools
- **DocumentETLTool**: Extract and transform document content (for file uploads only)
- **BlueprintGenerationTool**: Generate processing blueprints from content
- **GraphBuildTool**: Build knowledge graph from blueprints and extract relationships
- **MemoryGraphBuildTool**: Inherited from GraphBuildTool, process chat messages and generate personal blueprint; then build knowledge graph from blueprints and extract relationships

### Processing Pipeline Configuration
The `process_strategy` parameter allows you to customize the processing pipeline:

```json
{
  "pipeline": ["etl", "blueprint_gen", "graph_build"],
  "tool_configs": {
    "DocumentETLTool": {
      "max_file_size": 10485760,
      "supported_types": ["pdf", "md", "txt", "json"]
    },
    "BlueprintGenerationTool": {
      "max_chunk_size": 4000,
      "overlap": 200
    },
    "GraphBuildTool": {
      "max_triplets": 100,
      "confidence_threshold": 0.8
    }
  }
}
```
```
