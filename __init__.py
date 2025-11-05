"""
OCR Processor Package
Batch process OCR documents with GPT-5 API
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .config import Config, ConfigLoader
from .processor import OCRProcessor
from .api_client import OpenAIClient
from .state_manager import StateManager, ErrorLogger
from .validator import ResponseValidator

__all__ = [
    "Config",
    "ConfigLoader",
    "OCRProcessor",
    "OpenAIClient",
    "StateManager",
    "ErrorLogger",
    "ResponseValidator",
]
