# Knowledge Graph API

This module provides a REST API for the Knowledge Graph system, enabling document upload, processing, and querying for knowledge graph building.

## Quick Start

### 1. Install Dependencies

```bash
poetry install
pip install -r requirements-api.txt
```

### 2. Start the API Server

```bash
python run_api.py
```

The API will be available at `http://localhost:8000`

### 3. View API Documentation

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Upload Documents

**POST** `/api/v1/knowledge/upload`

Upload and process documents for knowledge graph building.

**Parameters:**
- `files`: One or more files (PDF, Markdown, TXT, SQL)
- `doc_link`: Link to original document (required)
- `topic_name`: Topic name for knowledge graph building (required)

**Example using curl:**

```bash
curl -X POST "http://localhost:8000/api/v1/knowledge/upload" \
  -F "files=@document.pdf" \
  -F "doc_link=https://docs.google.com/document/d/abc123" \
  -F "topic_name=project-alpha"
```

**Response:**
```json
{
  "status": "success",
  "message": "Documents uploaded successfully",
  "data": {
    "uploaded_count": 1,
    "documents": [
      {
        "id": "cc5b92b6-ef73-4c4d-8b54-60c610d3443d",
        "name": "document",
        "file_path": "uploads/document/document.pdf",
        "doc_link": "https://docs.google.com/document/d/abc123",
        "file_type": "pdf",
        "status": "processed"
      }
    ],
    "failed": []
  }
}
```

**Example using python:**

```python
import requests

url = "http://localhost:8000/api/v1/knowledge/upload"
file_path = "document.pdf"

with open(file_path, 'rb') as f:
    files = {'files': (file_path.split('/')[-1], f, 'application/pdf')}
    data = {
        'doc_link': "https://docs.google.com/document/d/abc123",
        'topic_name': "project-alpha"
    }
    response = requests.post(url, files=files, data=data)
    
print(response.status_code)
print(response.text)
```

### List Documents

**GET** `/api/v1/knowledge/`

Retrieve a list of documents with optional filtering and pagination.

**Query Parameters:**
- `topic_name`: Filter by topic name (exact match)
- `name`: Filter by document name (partial match)
- `doc_link`: Filter by original document link (exact match)
- `limit`: Maximum results (default 20, max 100)
- `offset`: Results offset (default 0)

**Example:**
```bash
curl "http://localhost:8000/api/v1/knowledge/?topic_name=project-alpha&limit=10"
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "documents": [
      {
        "id": "cc5b92b6-ef73-4c4d-8b54-60c610d3443d",
        "name": "document",
        "doc_link": "https://docs.google.com/document/d/abc123",
        "file_type": "pdf",
        "content_preview": "This document contains information about...",
        "created_at": "2024-01-15T10:30:00",
        "updated_at": "2024-01-15T10:30:00",
        "build_statuses": [
          {
            "topic_name": "project-alpha",
            "status": "completed",
            "created_at": "2024-01-15T10:30:00",
            "updated_at": "2024-01-15T10:35:00",
            "error_message": null
          }
        ],
        "graph_elements": {
          "entities": [
            {
              "id": "entity-123",
              "name": "Project Alpha",
              "description": "Main project entity"
            }
          ],
          "relationships": [
            {
              "id": "rel-456",
              "name": "entity-123 -> entity-789",
              "description": "Project relationship"
            }
          ]
        }
      }
    ],
    "total": 1,
    "limit": 10,
    "offset": 0,
    "has_more": false
  }
}
```

### Get Document Details

**GET** `/api/v1/knowledge/{document_id}`

Retrieve detailed information about a specific document.

**Example:**
```bash
curl "http://localhost:8000/api/v1/knowledge/cc5b92b6-ef73-4c4d-8b54-60c610d3443d"
```

**Response:**
Same structure as individual document in the list response above.

## Configuration

### Supported File Types
- PDF (`.pdf`) → document
- Markdown (`.md`) → document  
- Text (`.txt`) → document
- SQL (`.sql`) → code

### File Size Limits
- Maximum file size: 10MB per file

### Required Metadata for upload file
- **doc_link**: Link to the original document (required)
- **topic_name**: Topic name for knowledge graph building (required)
