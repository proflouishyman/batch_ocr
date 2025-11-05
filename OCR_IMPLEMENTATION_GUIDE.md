# OCR Document Processing Package - Implementation Guide

## Overview
A modular, production-ready Python package for batch processing OCR documents with GPT-5 API. Processes thousands of images asynchronously with intelligent batching, comprehensive error handling, progress tracking, and persistent state management.

---

## Architecture & Design Decisions

### Key Features
- **Async Processing**: Non-blocking concurrent API calls with rate limiting
- **Smart Batching**: Configurable batch sizes (default 25) with automatic queue management
- **State Persistence**: CSV-based tracking of processed files to avoid re-processing
- **Error Recovery**: 3-tier retry mechanism with exponential backoff
- **JSON Validation**: Response validation before persistence; re-submission on validation failure
- **Progress Tracking**: Detailed console output with ETA, token counts, and cost estimation
- **Modular Design**: Separate concerns for config, API, processing, and logging
- **CLI Menu**: Interactive startup menu for different processing modes

### API Strategy
- **Model**: `gpt-5-mini` (specified in config, switchable)
- **Endpoint**: Chat Completions API (`/v1/chat/completions`) for reliability
- **Image Format**: Base64-encoded (no external URL dependencies)
- **Response Format**: Structured JSON with NER, OCR variants, and categories
- **Polling**: Async task tracking with configurable poll intervals

---

## Folder Structure

```
ocr-processor/
├── README.md                          # User-facing documentation
├── LICENSE                            # MIT/Apache 2.0
├── setup.py                           # Package installer
├── requirements.txt                   # Dependencies
├── config.txt                         # User configuration (DO NOT commit)
├── processed_files.csv                # State tracking (DO NOT commit)
├── error_log.json                     # Error log (DO NOT commit)
│
├── ocr_processor/                     # Main package
│   ├── __init__.py
│   ├── config.py                      # Config loader & validation
│   ├── logger.py                      # Logging setup
│   ├── api_client.py                  # OpenAI API wrapper
│   ├── processor.py                   # Core processing logic
│   ├── validator.py                   # JSON response validation
│   ├── state_manager.py               # CSV tracking & state
│   ├── batch_queue.py                 # Async batch management
│   ├── menu.py                        # CLI menu handler
│   └── utils.py                       # Helper functions
│
├── examples/                          # Example usage
│   ├── sample_documents/              # Sample PDFs/images for testing
│   ├── example_output/                # Example JSON outputs
│   └── quick_start.py                 # Quick start script
│
└── tests/                             # Unit tests (optional)
    ├── test_config.py
    ├── test_validator.py
    └── test_state_manager.py
```

---

## Core Components Breakdown

### 1. **config.py** - Configuration Management
- Loads from `config.txt` (same directory as script)
- Validates all settings on startup
- Provides getters for all config values
- Supports environment variable overrides

### 2. **logger.py** - Logging & Progress
- Console output with timestamps
- File logging to `ocr_processor.log`
- Progress bar with ETA
- Token/cost tracking
- Color-coded severity levels

### 3. **api_client.py** - OpenAI Integration
- Async API calls using `aiohttp`
- Automatic retry with exponential backoff (3 retries)
- Token counting for cost estimation
- Error classification (rate limit, timeout, validation, etc.)
- Maintains rate limit headers awareness

### 4. **processor.py** - Main Processing Engine
- Orchestrates entire workflow
- Reads images from input folder
- Manages async task queue (batch size 25)
- Polls for completion
- Handles output JSON writing
- Tracks progress in real-time

### 5. **validator.py** - Response Validation
- Validates JSON schema against expected fields
- Checks for required OCR fields (raw, corrected)
- Validates NER output structure
- Verifies categorical data
- Re-submission logic on validation failure

### 6. **state_manager.py** - Persistent State
- CSV format: `filename, status, timestamp, api_request_id, error_count`
- Prevents re-processing of completed files
- Tracks failures for re-attempt mode
- Reads/writes atomically

### 7. **batch_queue.py** - Async Batching
- Manages task queue with configurable batch size
- Respects rate limits
- Submits batches sequentially, polls async
- Tracks in-flight requests

### 8. **menu.py** - CLI Interface
- Interactive menu at startup
- Options:
  1. Process new images only
  2. Reprocess everything
  3. Retry failed files
  4. Continue where it left off
  5. Exit

---

## Configuration File (config.txt)

```ini
# ============================================
# OCR PROCESSOR CONFIGURATION
# ============================================

# API Configuration
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
API_BASE_URL=https://api.openai.com/v1
MODEL=gpt-5-mini
API_TIMEOUT_SECONDS=60

# Image Processing
INPUT_FOLDER=/path/to/images
OUTPUT_FOLDER=/path/to/images  # Same folder as input or separate
IMAGE_EXTENSIONS=.pdf,.png,.jpg,.jpeg,.tiff

# Batch Processing
BATCH_SIZE=25
MAX_CONCURRENT_REQUESTS=25
POLL_INTERVAL_SECONDS=2
MAX_RETRIES=3
BACKOFF_MULTIPLIER=2.0

# GPT Prompt (customize for your use case)
SYSTEM_PROMPT=You are an expert OCR and NLP specialist. Process the provided document image with extreme precision.
USER_PROMPT_TEMPLATE=Extract and process this OCR document. Return ONLY valid JSON with these exact fields:
{
  "raw_ocr": "verbatim OCR output from image",
  "corrected_ocr": "grammatically corrected and cleaned OCR text",
  "ner": {
    "PERSON": [...],
    "ORG": [...],
    "GPE": [...],
    "DATE": [...],
    "MONEY": [...],
    "PERCENT": [...],
    "FACILITY": [...],
    "PRODUCT": [...],
    "EVENT": [...]
  },
  "categories": {
    "document_type": "detected type (invoice, receipt, contract, etc)",
    "confidence": 0.0-1.0,
    "language": "detected language code",
    "has_tables": true/false,
    "has_images": true/false,
    "page_count": number,
    "quality_score": 0-100
  }
}

# Logging
LOG_LEVEL=INFO
LOG_FILE=ocr_processor.log
VERBOSE_PROGRESS=true

# Resumption & State
STATE_FILE=processed_files.csv
ERROR_LOG_FILE=error_log.json
AUTO_RESUME=true

# Cost Tracking
TRACK_COSTS=true
ESTIMATED_INPUT_COST_PER_1K_TOKENS=0.003
ESTIMATED_OUTPUT_COST_PER_1K_TOKENS=0.006
```

---

## Expected JSON Output

Each processed image produces a JSON file named `{original_filename}.json`:

```json
{
  "filename": "document_001.pdf",
  "processing_timestamp": "2025-11-05T14:32:15Z",
  "api_request_id": "chatcmpl-xxxxxx",
  "tokens_used": {
    "input": 2048,
    "output": 512,
    "total": 2560
  },
  "estimated_cost": 0.0183,
  "raw_ocr": "This is the verbatim OCR output as extracted...",
  "corrected_ocr": "This is the grammatically corrected OCR text...",
  "ner": {
    "PERSON": ["John Smith", "Jane Doe"],
    "ORG": ["Acme Corp", "Tech Industries"],
    "GPE": ["New York", "California"],
    "DATE": ["2025-11-05", "January 1, 2025"],
    "MONEY": ["$1,234.56", "$99.99"],
    "PERCENT": ["50%", "25.5%"],
    "FACILITY": ["Building A", "Office 201"],
    "PRODUCT": ["Product XYZ"],
    "EVENT": ["Annual Meeting"]
  },
  "categories": {
    "document_type": "invoice",
    "confidence": 0.94,
    "language": "en",
    "has_tables": true,
    "has_images": false,
    "page_count": 3,
    "quality_score": 87
  }
}
```

---

## Processing Flow

```
┌─────────────────────────────────────────┐
│ 1. Load Config & Initialize             │
│    - Validate settings                  │
│    - Setup logging                      │
│    - Load state from CSV                │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 2. CLI Menu                             │
│    - New only / Reprocess / Retry / Etc │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 3. Discover Images                      │
│    - Scan input folder                  │
│    - Filter by extension                │
│    - Exclude already processed (if mode)│
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 4. Batch & Submit                       │
│    - Group into batches (25 max)        │
│    - Encode to base64                   │
│    - Submit async requests              │
│    - Track request IDs                  │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 5. Poll for Completion                  │
│    - Check status every N seconds       │
│    - Update progress display            │
│    - Show ETA & token counts            │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 6. Validate & Persist                   │
│    - Parse JSON response                │
│    - Validate schema                    │
│    - Write .json alongside image        │
│    - Update state CSV                   │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 7. Error Handling                       │
│    - If validation fails:               │
│      Retry (max 3 times)                │
│    - If API error:                      │
│      Backoff & retry                    │
│    - If persistent failure:             │
│      Log & mark for manual review       │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│ 8. Summary Report                       │
│    - Files processed                    │
│    - Failures & errors                  │
│    - Total tokens & cost                │
│    - Processing time                    │
└─────────────────────────────────────────┘
```

---

## CLI Menu Example

```
=====================================
  OCR PROCESSOR - Main Menu
=====================================
What would you like to do?

1. Process new images only
   (Skip files in processed_files.csv)

2. Reprocess everything
   (Reset state, start fresh)

3. Retry failed files only
   (Only files marked as ERROR)

4. Continue where we left off
   (Resume interrupted batch)

5. Exit

Select option [1-5]: _
```

---

## Error Handling Strategy

### Retry Mechanism (3 attempts)
1. **Attempt 1**: Immediate retry on transient errors
2. **Attempt 2**: Wait 2 seconds (backoff × 1), then retry
3. **Attempt 3**: Wait 4 seconds (backoff × 2), then retry
4. **Final**: Mark as ERROR, log details, move to next

### Error Classification
- **Rate Limit (429)**: Backoff & retry
- **Timeout (504, 408)**: Backoff & retry
- **Bad Request (400)**: Log, mark ERROR (no retry)
- **Invalid JSON**: Re-submit with same image
- **Validation Failure**: Retry up to 3 times, then ERROR
- **File I/O**: Log & continue

### Error Log Format (error_log.json)
```json
{
  "filename": "doc_001.pdf",
  "error_type": "validation_failure",
  "error_message": "Missing required field: ner",
  "attempt": 3,
  "timestamp": "2025-11-05T14:32:15Z",
  "api_request_id": "chatcmpl-xxx",
  "can_retry": false
}
```

---

## Progress Output Example

```
╔════════════════════════════════════════════════════════════════╗
║              OCR PROCESSOR - Processing Started               ║
╚════════════════════════════════════════════════════════════════╝

Batch 1/40 (25 images):
  [████████░░░░░░░░░░░░░░░░░░░░] 40%
  Time Elapsed: 00:05:32
  Estimated Time Remaining: 00:08:15
  Processed: 10/250
  Failed: 1 (document_015.pdf - validation_failure)

Token Usage (Running Total):
  Input Tokens: 23,456
  Output Tokens: 8,234
  Total: 31,690
  Estimated Cost: $0.38 / $2.50 budget

Current Status: Polling for batch completion...
Next Poll: in 2 seconds
```

---

## Resumption & State Management

### CSV Format (processed_files.csv)
```csv
filename,status,timestamp,api_request_id,error_count,notes
document_001.pdf,SUCCESS,2025-11-05T14:00:00Z,chatcmpl-xxx,0,
document_002.pdf,ERROR,2025-11-05T14:05:00Z,chatcmpl-yyy,3,validation_failure
document_003.pdf,PENDING,2025-11-05T14:10:00Z,chatcmpl-zzz,0,
```

### States
- `PENDING`: Submitted, waiting for response
- `SUCCESS`: Processed, JSON written
- `ERROR`: Failed after max retries
- `SKIPPED`: Excluded by mode selection

---

## Sensible Defaults (config.txt)

```ini
# These are recommended starting values:
BATCH_SIZE=25                          # Optimal for most use cases
MAX_RETRIES=3                          # Standard retry count
BACKOFF_MULTIPLIER=2.0                 # Exponential backoff
POLL_INTERVAL_SECONDS=2                # Balance speed vs. API load
API_TIMEOUT_SECONDS=60                 # Reasonable timeout
LOG_LEVEL=INFO                         # Balanced verbosity
TRACK_COSTS=true                       # Always track for budget
AUTO_RESUME=true                       # Robustness on failure
```

---

## Key Implementation Notes

### Why Option B Async?
- Submit all tasks immediately (respecting rate limits)
- Single polling loop monitors everything
- Scales well to thousands of images
- Batch size limits concurrent submissions, not polling

### Base64 Strategy
- Encode images synchronously (small memory footprint)
- Decode once per image, not repeatedly
- No external URL/storage dependencies
- Cleaner error handling (all data local)

### CSV vs. Database
- Simple, human-readable state
- No DB dependency (pip install less complex)
- Easy to inspect/debug manually
- CSV is sufficient for millions of records

### Cost Tracking
- Token counters on every response
- Estimated cost based on pricing in config
- Real-time budget monitoring
- Helps optimize batch sizes & model choice

---

## Installation & Quick Start

```bash
# Install package
pip install -e .

# Copy config template
cp config.txt.example config.txt

# Edit config with your API key and paths
nano config.txt

# Run
python -m ocr_processor
```

See README.md for detailed setup instructions and examples.
