"""
state_manager.py - State persistence and tracking
Manages CSV-based tracking of processed files
"""

import csv
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime
import json


class FileState:
    """Represents the state of a single file"""
    
    def __init__(
        self,
        filename: str,
        status: str,  # PENDING, SUCCESS, ERROR, SKIPPED
        timestamp: Optional[str] = None,
        api_request_id: Optional[str] = None,
        error_count: int = 0,
        notes: str = ""
    ):
        self.filename = filename
        self.status = status
        self.timestamp = timestamp or datetime.utcnow().isoformat() + "Z"
        self.api_request_id = api_request_id or ""
        self.error_count = error_count
        self.notes = notes
    
    def to_csv_row(self) -> List[str]:
        """Convert to CSV row"""
        return [
            self.filename,
            self.status,
            self.timestamp,
            self.api_request_id,
            str(self.error_count),
            self.notes
        ]
    
    @staticmethod
    def from_csv_row(row: List[str]) -> "FileState":
        """Create from CSV row"""
        return FileState(
            filename=row[0],
            status=row[1],
            timestamp=row[2],
            api_request_id=row[3],
            error_count=int(row[4]) if row[4] else 0,
            notes=row[5] if len(row) > 5 else ""
        )


class StateManager:
    """Manages persistent state of processed files"""
    
    CSV_HEADERS = ["filename", "status", "timestamp", "api_request_id", "error_count", "notes"]
    
    def __init__(self, state_file: str = "processed_files.csv"):
        self.state_file = Path(state_file)
        self.state: Dict[str, FileState] = {}
        self._load_from_csv()
    
    def _load_from_csv(self):
        """Load state from CSV file if it exists"""
        if not self.state_file.exists():
            return
        
        try:
            with open(self.state_file, "r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                for row in reader:
                    if len(row) >= 2:
                        state = FileState.from_csv_row(row)
                        self.state[state.filename] = state
        
        except Exception as e:
            print(f"Warning: Could not load state file: {e}")
    
    def save_to_csv(self):
        """Write state to CSV file"""
        try:
            with open(self.state_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)
                
                for state in self.state.values():
                    writer.writerow(state.to_csv_row())
        
        except Exception as e:
            print(f"Error: Could not save state file: {e}")
            raise
    
    def mark_pending(self, filename: str, request_id: str = ""):
        """Mark file as pending processing"""
        self.state[filename] = FileState(
            filename=filename,
            status="PENDING",
            api_request_id=request_id
        )
    
    def mark_success(self, filename: str, request_id: str = "", input_tokens: int = 0, output_tokens: int = 0):
        """Mark file as successfully processed"""
        self.state[filename] = FileState(
            filename=filename,
            status="SUCCESS",
            timestamp=datetime.utcnow().isoformat() + "Z",
            api_request_id=request_id,
            notes=f"Tokens: {input_tokens}in/{output_tokens}out"
        )
    
    def mark_error(self, filename: str, error_msg: str = "", request_id: str = ""):
        """Mark file as having an error"""
        existing = self.state.get(filename)
        error_count = (existing.error_count if existing else 0) + 1
        
        self.state[filename] = FileState(
            filename=filename,
            status="ERROR",
            timestamp=datetime.utcnow().isoformat() + "Z",
            api_request_id=request_id or (existing.api_request_id if existing else ""),
            error_count=error_count,
            notes=error_msg[:200] if error_msg else ""
        )
    
    def mark_skipped(self, filename: str, reason: str = ""):
        """Mark file as skipped"""
        self.state[filename] = FileState(
            filename=filename,
            status="SKIPPED",
            notes=reason
        )
    
    def get_status(self, filename: str) -> Optional[str]:
        """Get status of a file"""
        if filename in self.state:
            return self.state[filename].status
        return None
    
    def is_processed(self, filename: str) -> bool:
        """Check if file has been processed (success or error)"""
        status = self.get_status(filename)
        return status in ["SUCCESS", "ERROR", "SKIPPED"]
    
    def get_processed_files(self) -> Set[str]:
        """Get set of processed filenames"""
        return {
            name for name, state in self.state.items()
            if state.status in ["SUCCESS", "ERROR", "SKIPPED"]
        }
    
    def get_failed_files(self) -> List[str]:
        """Get list of failed filenames"""
        return [
            name for name, state in self.state.items()
            if state.status == "ERROR"
        ]
    
    def get_pending_files(self) -> List[str]:
        """Get list of pending filenames"""
        return [
            name for name, state in self.state.items()
            if state.status == "PENDING"
        ]
    
    def get_file_error_count(self, filename: str) -> int:
        """Get error count for a file"""
        if filename in self.state:
            return self.state[filename].error_count
        return 0
    
    def clear(self):
        """Clear all state"""
        self.state = {}
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about current state"""
        stats = {
            "total": len(self.state),
            "success": 0,
            "error": 0,
            "pending": 0,
            "skipped": 0
        }
        
        for state in self.state.values():
            if state.status == "SUCCESS":
                stats["success"] += 1
            elif state.status == "ERROR":
                stats["error"] += 1
            elif state.status == "PENDING":
                stats["pending"] += 1
            elif state.status == "SKIPPED":
                stats["skipped"] += 1
        
        return stats


class ErrorLogger:
    """Manages error log in JSON format"""
    
    def __init__(self, error_log_file: str = "error_log.json"):
        self.error_log_file = Path(error_log_file)
        self.errors: List[Dict] = []
        self._load_from_json()
    
    def _load_from_json(self):
        """Load error log from JSON file if it exists"""
        if not self.error_log_file.exists():
            return
        
        try:
            with open(self.error_log_file, "r", encoding="utf-8") as f:
                self.errors = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load error log: {e}")
    
    def save_to_json(self):
        """Write error log to JSON file"""
        try:
            with open(self.error_log_file, "w", encoding="utf-8") as f:
                json.dump(self.errors, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error: Could not save error log: {e}")
            raise
    
    def log_error(
        self,
        filename: str,
        error_type: str,
        error_message: str,
        attempt: int = 1,
        request_id: str = "",
        can_retry: bool = True,
        payload_path: str = ""
    ):
        """Log an error"""
        error_entry = {
            "filename": filename,
            "error_type": error_type,
            "error_message": error_message[:500],
            "attempt": attempt,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
            "can_retry": can_retry,
            "payload_path": payload_path
        }
        
        self.errors.append(error_entry)
    
    def get_errors_for_file(self, filename: str) -> List[Dict]:
        """Get all errors for a specific file"""
        return [e for e in self.errors if e["filename"] == filename]
    
    def get_error_summary(self) -> Dict[str, int]:
        """Get summary of errors by type"""
        summary = {}
        for error in self.errors:
            error_type = error.get("error_type", "unknown")
            summary[error_type] = summary.get(error_type, 0) + 1
        return summary

    def clear_errors_for(self, filename: str):
        """Remove any logged errors for a specific filename (useful when a
        file later succeeds and you want the error summary to reflect only
        unresolved/current errors).
        """
        try:
            self.errors = [e for e in self.errors if e.get("filename") != filename]
        except Exception:
            # Defensive: if something unexpected is in errors, fallback to no-op
            pass
    
    def clear(self):
        """Clear all error logs"""
        self.errors = []
