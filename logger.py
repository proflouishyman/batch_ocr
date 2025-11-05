"""
logger.py - Logging and progress tracking
Handles console output, file logging, and progress visualization
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import time


class ProgressTracker:
    """Tracks processing progress and estimates time remaining"""
    
    def __init__(self, total_files: int, verbose: bool = True):
        self.total_files = total_files
        self.verbose = verbose
        self.processed = 0
        self.failed = 0
        self.start_time = time.time()
        self.batch_start_time = time.time()
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
    
    def update(self, success: bool = True, input_tokens: int = 0, output_tokens: int = 0, cost: float = 0.0):
        """Update progress with token and cost info"""
        if success:
            self.processed += 1
        else:
            self.failed += 1
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_cost += cost
    
    def get_elapsed_time(self) -> str:
        """Get formatted elapsed time"""
        elapsed = time.time() - self.start_time
        return self._format_duration(elapsed)
    
    def get_remaining_time(self) -> str:
        """Estimate and return remaining time"""
        if self.processed == 0:
            return "N/A"
        
        elapsed = time.time() - self.start_time
        avg_per_file = elapsed / self.processed
        remaining_files = max(0, self.total_files - self.processed)
        estimated_remaining = avg_per_file * remaining_files
        
        return self._format_duration(estimated_remaining)
    
    def get_progress_bar(self, width: int = 30) -> str:
        """Generate ASCII progress bar"""
        if self.total_files == 0:
            return "N/A"
        
        percent = self.processed / self.total_files
        filled = int(width * percent)
        bar = "█" * filled + "░" * (width - filled)
        percent_str = f"{percent * 100:.0f}%"
        
        return f"[{bar}] {percent_str}"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class OCRLogger:
    """Central logger for OCR processing with progress tracking"""
    
    def __init__(self, log_file: str = "ocr_processor.log", log_level: str = "INFO", verbose: bool = True):
        self.log_file = Path(log_file)
        self.verbose = verbose
        self.progress: Optional[ProgressTracker] = None
        
        # Setup root logger
        self.logger = logging.getLogger("ocr_processor")
        self.logger.setLevel(getattr(logging, log_level))
        
        # File handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(getattr(logging, log_level))
        
        # Console handler (only for INFO and above if verbose)
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG if verbose else logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def init_progress(self, total_files: int):
        """Initialize progress tracker"""
        self.progress = ProgressTracker(total_files, self.verbose)
        self.info(f"Starting processing of {total_files} files")
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)
    
    def print_header(self, title: str):
        """Print formatted header"""
        if self.verbose:
            width = 62
            print("\n╔" + "═" * (width - 2) + "╗")
            print(f"║ {title:^{width - 4}} ║")
            print("╚" + "═" * (width - 2) + "╝\n")
    
    def print_progress_update(self, batch_num: int, total_batches: int, batch_size: int, failed_count: int = 0):
        """Print detailed progress update"""
        if not self.verbose or self.progress is None:
            return
        
        print(f"\nBatch {batch_num}/{total_batches} ({batch_size} images):")
        print(f"  {self.progress.get_progress_bar()}")
        print(f"  Time Elapsed: {self.progress.get_elapsed_time()}")
        print(f"  Est. Time Remaining: {self.progress.get_remaining_time()}")
        print(f"  Processed: {self.progress.processed}/{self.progress.total_files}")
        
        if failed_count > 0:
            print(f"  Failed: {failed_count}")
        
        print(f"\nToken Usage (Running Total):")
        print(f"  Input Tokens: {self.progress.total_input_tokens:,}")
        print(f"  Output Tokens: {self.progress.total_output_tokens:,}")
        print(f"  Total: {self.progress.total_input_tokens + self.progress.total_output_tokens:,}")
        print(f"  Estimated Cost: ${self.progress.total_cost:.2f}")
    
    def print_summary(self):
        """Print final processing summary"""
        if not self.progress:
            return
        
        self.print_header("Processing Complete")
        
        print("Final Summary:")
        print(f"  Total Files: {self.progress.total_files}")
        print(f"  Successfully Processed: {self.progress.processed}")
        print(f"  Failed: {self.progress.failed}")
        print(f"  Total Time: {self.progress.get_elapsed_time()}")
        print(f"\nToken Summary:")
        print(f"  Input Tokens: {self.progress.total_input_tokens:,}")
        print(f"  Output Tokens: {self.progress.total_output_tokens:,}")
        print(f"  Total Tokens: {self.progress.total_input_tokens + self.progress.total_output_tokens:,}")
        print(f"  Estimated Total Cost: ${self.progress.total_cost:.2f}")
        print(f"\nSuccess Rate: {(self.progress.processed / max(1, self.progress.total_files)) * 100:.1f}%")
        print(f"Log file: {self.log_file.absolute()}\n")
    
    def print_status(self, message: str):
        """Print status message (won't go to file)"""
        if self.verbose:
            print(f"\n  Status: {message}")
