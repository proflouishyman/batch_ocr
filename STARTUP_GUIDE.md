# OCR Processor - Startup Guide

Complete step-by-step setup instructions to get started in under 10 minutes.

## Prerequisites

- Python 3.8 or higher
- OpenAI API key (from https://platform.openai.com/account/api-keys)
- Folder of images to process (PDF, PNG, JPG, TIFF)

## Installation Steps

### 1. Get Your API Key

```
1. Go to https://platform.openai.com/account/api-keys
2. Click "Create new secret key"
3. Copy the key (starts with "sk-")
4. Keep this safe - don't share it!
```

### 2. Create Project Folder

```bash
# Create a new folder for the project
mkdir ocr-processor
cd ocr-processor

# Download all files from the package into this folder
# You should have:
# - config.py
# - logger.py
# - api_client.py
# - validator.py
# - state_manager.py
# - menu.py
# - processor.py
# - setup.py
# - requirements.txt
# - config.txt.example
# - README.md
```

### 3. Install Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt

# This installs:
# - aiohttp (for async API calls)
# - configparser (for config files)
# - python-dotenv (optional, for .env files)
```

### 4. Create Configuration File

```bash
# Copy the example config
cp config.txt.example config.txt

# Open in text editor and edit
nano config.txt
# or on Windows:
# notepad config.txt
```

### 5. Configure Your Settings

Edit `config.txt` and fill in these essential values:

```ini
# Line 1: Your API key
OPENAI_API_KEY=sk-your-actual-key-here

# Line 5: Where your images are stored (full path)
INPUT_FOLDER=/path/to/your/images

# Line 8: Where to save JSON results (can be same as INPUT_FOLDER)
OUTPUT_FOLDER=/path/to/your/images

# Line 11: Model choice
MODEL=gpt-5-mini
```

**Example on macOS:**
```ini
OPENAI_API_KEY=sk-proj-abc123xyz...
INPUT_FOLDER=/Users/yourname/Documents/invoices
OUTPUT_FOLDER=/Users/yourname/Documents/invoices
MODEL=gpt-5-mini
```

**Example on Windows:**
```ini
OPENAI_API_KEY=sk-proj-abc123xyz...
INPUT_FOLDER=C:\Users\yourname\Documents\invoices
OUTPUT_FOLDER=C:\Users\yourname\Documents\invoices
MODEL=gpt-5-mini
```

**Example on Linux:**
```ini
OPENAI_API_KEY=sk-proj-abc123xyz...
INPUT_FOLDER=/home/username/documents/invoices
OUTPUT_FOLDER=/home/username/documents/invoices
MODEL=gpt-5-mini
```

### 6. Prepare Your Images

Create or copy images into your INPUT_FOLDER:

```bash
# Example folder structure
/your/image/folder/
├── invoice_001.pdf
├── invoice_002.pdf
├── receipt_001.jpg
└── contract_001.pdf
```

Supported formats: `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`

### 7. Test with Sample Images

First, test with just 5 images:

```bash
# Copy 5 test images to a test folder
mkdir test_images
cp /your/image/folder/invoice_{001..005}.pdf test_images/

# Update config.txt to point to test folder
# INPUT_FOLDER=/path/to/test_images
```

### 8. Run the Processor

```bash
# Navigate to the project folder
cd /path/to/ocr-processor

# Run the processor
python processor.py

# You'll see the interactive menu:
# =============================================
#   OCR PROCESSOR - Main Menu
# =============================================
# What would you like to do?
# 1. Process new images only
# 2. Reprocess everything
# 3. Retry failed files only
# 4. Continue where we left off
# 5. Exit
```

### 9. Choose Processing Mode

For your first run, select **Option 1** (Process new images only):

```
Select option [1-5]: 1
✓ Processing NEW images only (skipping processed files)
```

### 10. Monitor Progress

Watch the real-time progress:

```
Batch 1/1 (5 images):
  [████████████████████████████░] 90%
  Time Elapsed: 00:02:15
  Est. Time Remaining: 00:00:15
  Processed: 4/5
  Failed: 0

Token Usage (Running Total):
  Input Tokens: 8,456
  Output Tokens: 2,234
  Total: 10,690
  Estimated Cost: $0.06
```

## Checking Results

### 1. View JSON Output Files

After processing, you'll find `.json` files in your OUTPUT_FOLDER:

```bash
# List the output files
ls /path/to/images/*.json

# View a sample result
cat /path/to/images/invoice_001.json | python -m json.tool
```

### 2. Check Processing Status

Three files track the processing:

**processed_files.csv** - Which files completed
```bash
cat processed_files.csv
# Shows: filename, status, timestamp, api_request_id, error_count, notes
```

**error_log.json** - Details about any errors
```bash
cat error_log.json | python -m json.tool
```

**ocr_processor.log** - Detailed processing log
```bash
tail -50 ocr_processor.log
```

## Scaling to Production

### Once Testing is Complete:

1. **Point to all your images:**
   - Update `INPUT_FOLDER` in config.txt to your full image directory
   - Keep `OUTPUT_FOLDER` pointing to the same location

2. **Run with all images:**
   ```bash
   python processor.py
   # Select option 1 (new images only)
   ```

3. **Monitor in background (optional):**
   ```bash
   # On macOS/Linux
   nohup python processor.py > processor.log 2>&1 &
   
   # Or use screen
   screen -S ocr-processor
   python processor.py
   # Press Ctrl+A then D to detach
   ```

### Performance Tuning:

For large batches (1,000+ images), edit config.txt:

```ini
# Increase batch size for faster processing
BATCH_SIZE=50  # Instead of 25

# Use cheaper/faster model if quality permits
MODEL=gpt-5-nano  # Faster and cheaper than gpt-5-mini

# Reduce polling interval
POLL_INTERVAL_SECONDS=1  # Check status every 1 second
```

## Resuming Processing

If the processor stops or crashes:

```bash
# Just run it again and select option 4
python processor.py
Select option [1-5]: 4  # Continue where we left off

# The system will:
# - Skip all successfully processed files
# - Skip all skipped files
# - Reprocess any pending files
# - Reprocess any failed files
```

## Common Issues & Solutions

### "API key not found"
```
Solution: Make sure OPENAI_API_KEY is in config.txt
Run: grep OPENAI_API_KEY config.txt
```

### "No images found"
```
Solution: Check INPUT_FOLDER exists
Run: ls -la /path/to/images/
```

### "Request timeout"
```
Solution: Increase API_TIMEOUT_SECONDS in config.txt
Change: API_TIMEOUT_SECONDS=60
To: API_TIMEOUT_SECONDS=120
```

### "Rate limited (429)"
```
Solution: Reduce BATCH_SIZE in config.txt
Change: BATCH_SIZE=25
To: BATCH_SIZE=10
```

## Next Steps

1. ✅ **Setup complete!** You're ready to process images
2. 📊 **Test with samples** - Start with 5-10 images
3. 🚀 **Scale up** - Process your full batch
4. 💾 **Integrate** - Read the JSON outputs for downstream processing
5. 📖 **Learn more** - See README.md for advanced features

## Getting Help

If you run into issues:

1. **Check the logs:**
   ```bash
   tail -100 ocr_processor.log
   cat error_log.json
   grep your_filename processed_files.csv
   ```

2. **Verify configuration:**
   ```bash
   grep -E "^[A-Z]" config.txt | head -20
   ```

3. **Test API key:**
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer sk-your-key-here"
   ```

4. **Check dependencies:**
   ```bash
   pip list | grep -E "aiohttp|configparser"
   ```

## You're All Set! 🎉

Ready to process your documents:

```bash
cd /path/to/ocr-processor
python processor.py
```

Select option 1 and watch the magic happen!

---

**Questions?** Refer to README.md or OCR_IMPLEMENTATION_GUIDE.md for detailed documentation.
