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

### Enhanced Data Processing Pipeline

**POST** `/api/v1/save_pipeline`

Enhanced endpoint for saving and processing data using the tools pipeline system. Supports both file uploads and JSON input with configurable processing strategies and detailed execution tracking.

**Content-Type Support:**
- `multipart/form-data`: For file uploads
- `application/json`: For JSON data input

#### For File Uploads (`multipart/form-data`):

**Parameters:**
- `file`: The file to be uploaded (required)
- `metadata`: JSON string containing processing metadata (required)
  - `topic_name`: Topic name for knowledge graph building
  - `link`: Original document link
  - Additional custom metadata fields
- `target_type`: Processing target type (required, e.g., "knowledge_graph")
- `process_strategy`: JSON string with processing pipeline configuration (optional)
  - `pipeline`: Array of tool names to execute in sequence
  - Example: `{"pipeline": ["etl", "blueprint_gen", "graph_build"]}`

**Example using curl:**
```bash
curl -X POST "http://localhost:8000/api/v1/save_pipeline" \
  -F "file=@document.pdf" \
  -F 'metadata={"topic_name":"study","link":"https://example.com/doc"}' \
  -F "target_type=knowledge_graph" \
  -F 'process_strategy={"pipeline":["etl","blueprint_gen","graph_build"]}'
```

**Response:**
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

#### For JSON Input (`application/json`):

**Parameters:**
- `input`: The raw data to process - can be chat history array or any JSON data (required)
- `metadata`: JSON object with processing context (required)
  - `user_id`: User identifier for personal memory processing
  - Additional context fields as needed
- `target_type`: Processing target type (required, e.g., "personal_memory")
- `process_strategy`: JSON object with processing pipeline configuration (optional)
  - `pipeline`: Array of tool names to execute
  - For JSON input, use `["blueprint_gen", "graph_build"]` (ETL not needed)

**Example using curl (chat history):**
```bash
curl -X POST "http://localhost:8000/api/v1/save_pipeline" \
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

**Example using curl (raw JSON data):**
```bash
curl -X POST "http://localhost:8000/api/v1/save_pipeline" \
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

### Available Pipeline Tools
- **DocumentETLTool**: Extract and transform document content (for file uploads only)
- **BlueprintGenerationTool**: Generate processing blueprints from content
- **GraphBuildTool**: Build knowledge graph from blueprints and extract relationships

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