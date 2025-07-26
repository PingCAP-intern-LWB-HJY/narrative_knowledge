# Test Script for process_request() Function

This directory contains a comprehensive test suite for testing the `process_request()` function in three different scenarios.

## Files Created

1. `test_process_request.py` - Main test script with three scenarios
2. `run_tests.sh` - Simple bash runner script
3. `test_requirements.txt` - Optional dependencies

## Test Scenarios

### Scenario 1: Adding Single Document to Existing Topic
- **Purpose**: Test processing a single document into an existing knowledge graph topic
- **Configuration**: `is_new_topic: False`
- **Files**: 1 test document

### Scenario 2: Adding Batch Documents to Existing Topic  
- **Purpose**: Test processing multiple documents into an existing topic
- **Configuration**: `is_new_topic: False`, `batch_processing: True`
- **Files**: 3 test documents

### Scenario 3: Creating New Topic with Batch Documents
- **Purpose**: Test creating a new topic with multiple documents
- **Configuration**: `is_new_topic: True`, `batch_processing: True` 
- **Files**: 2 test documents with unique topic name

## How to Run the Tests

### Method 1: Direct Python
```bash
cd /Users/hjy/Downloads/test
python3 test_process_request.py
```

### Method 2: Using the Runner Script
```bash
cd /Users/hjy/Downloads/test
./run_tests.sh
```

## Mock Objects

The test script includes mock implementations for:
- **MockLLMClient**: Simulates LLM responses
- **MockEmbeddingFunc**: Generates deterministic embeddings

## Test Output

Each test scenario provides:
- ✅/❌ Success status
- Execution ID for tracking
- Processing messages
- Data structure information
- Files processed count

## Cleanup

The test script automatically:
- Creates temporary test files
- Cleans up files after execution
- Provides detailed error messages for debugging

## Dependencies

Basic Python 3.x required. Optional dependencies listed in `test_requirements.txt`.