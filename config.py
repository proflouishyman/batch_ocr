"""
config.py - Configuration management for OCR processor
Loads and validates settings from config.txt in the same directory
"""

import os
import configparser
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration container with all settings"""
    
    # API Configuration
    openai_api_key: str
    api_base_url: str
    model: str
    api_timeout_seconds: int
    
    # Image Processing
    input_folder: Path
    output_folder: Path
    image_extensions: list
    
    # Batch Processing
    batch_size: int
    max_concurrent_requests: int
    poll_interval_seconds: float
    max_retries: int
    backoff_multiplier: float
    
    # Prompts
    system_prompt: str
    user_prompt_template: str
    
    # Logging
    log_level: str
    log_file: str
    verbose_progress: bool
    
    # State Management
    state_file: str
    error_log_file: str
    auto_resume: bool
    
    # Cost Tracking
    track_costs: bool
    estimated_input_cost_per_1k_tokens: float
    estimated_output_cost_per_1k_tokens: float


class ConfigLoader:
    """Loads and validates configuration from config.txt"""
    
    DEFAULT_CONFIG_FILENAME = "config.txt"
    
    # Default values for sensible defaults
    DEFAULTS = {
        "BATCH_SIZE": "25",
        "MAX_CONCURRENT_REQUESTS": "25",
        "POLL_INTERVAL_SECONDS": "2",
        "MAX_RETRIES": "3",
        "BACKOFF_MULTIPLIER": "2.0",
        "API_TIMEOUT_SECONDS": "60",
        "LOG_LEVEL": "INFO",
        "VERBOSE_PROGRESS": "true",
        "AUTO_RESUME": "true",
        "TRACK_COSTS": "true",
        "ESTIMATED_INPUT_COST_PER_1K_TOKENS": "0.003",
        "ESTIMATED_OUTPUT_COST_PER_1K_TOKENS": "0.006",
        "API_BASE_URL": "https://api.openai.com/v1",
        "MODEL": "gpt-5-mini",
        "IMAGE_EXTENSIONS": ".pdf,.png,.jpg,.jpeg,.tiff",
        "LOG_FILE": "ocr_processor.log",
        "STATE_FILE": "processed_files.csv",
        "ERROR_LOG_FILE": "error_log.json",
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config loader.
        
        Args:
            config_path: Path to config file. If None, looks for config.txt in current directory.
        
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required settings are missing or invalid
        """
        if config_path is None:
            config_path = self.DEFAULT_CONFIG_FILENAME
        
        self.config_path = Path(config_path)
        
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {self.config_path.absolute()}\n"
                "Please create a config.txt file in the same directory as this script.\n"
                "See config.txt.example for a template."
            )
        
        self.parser = configparser.ConfigParser()
        self.parser.read(self.config_path)
    
    def load(self) -> Config:
        """
        Load and validate configuration.
        
        Returns:
            Config object with all settings
        
        Raises:
            ValueError: If required settings are missing or invalid
        """
        
        # API Configuration
        openai_api_key = self._get_required("OPENAI_API_KEY")
        if not openai_api_key.startswith("sk-"):
            raise ValueError("OPENAI_API_KEY must start with 'sk-'")
        
        api_base_url = self._get("API_BASE_URL")
        model = self._get("MODEL")
        api_timeout = self._get_int("API_TIMEOUT_SECONDS")
        
        # Image Processing
        input_folder = self._get_path_required("INPUT_FOLDER")
        if not input_folder.exists():
            raise ValueError(f"INPUT_FOLDER does not exist: {input_folder}")
        if not input_folder.is_dir():
            raise ValueError(f"INPUT_FOLDER is not a directory: {input_folder}")
        
        output_folder = self._get_path_required("OUTPUT_FOLDER")
        output_folder.mkdir(parents=True, exist_ok=True)
        
        image_extensions = self._get("IMAGE_EXTENSIONS").split(",")
        image_extensions = [ext.strip().lower() for ext in image_extensions]
        
        # Batch Processing
        batch_size = self._get_int("BATCH_SIZE")
        if batch_size < 1:
            raise ValueError("BATCH_SIZE must be >= 1")
        
        max_concurrent = self._get_int("MAX_CONCURRENT_REQUESTS")
        if max_concurrent < 1:
            raise ValueError("MAX_CONCURRENT_REQUESTS must be >= 1")
        
        poll_interval = self._get_float("POLL_INTERVAL_SECONDS")
        if poll_interval <= 0:
            raise ValueError("POLL_INTERVAL_SECONDS must be > 0")
        
        max_retries = self._get_int("MAX_RETRIES")
        if max_retries < 0:
            raise ValueError("MAX_RETRIES must be >= 0")
        
        backoff_mult = self._get_float("BACKOFF_MULTIPLIER")
        if backoff_mult <= 1:
            raise ValueError("BACKOFF_MULTIPLIER must be > 1")
        
        # Prompts
        system_prompt = self._get_required("SYSTEM_PROMPT")
        user_prompt_template = self._get_required("USER_PROMPT_TEMPLATE")
        
        # Logging
        log_level = self._get("LOG_LEVEL").upper()
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError(f"Invalid LOG_LEVEL: {log_level}")
        
        log_file = self._get("LOG_FILE")
        verbose = self._get_bool("VERBOSE_PROGRESS")
        
        # State Management
        state_file = self._get("STATE_FILE")
        error_log_file = self._get("ERROR_LOG_FILE")
        auto_resume = self._get_bool("AUTO_RESUME")
        
        # Cost Tracking
        track_costs = self._get_bool("TRACK_COSTS")
        input_cost = self._get_float("ESTIMATED_INPUT_COST_PER_1K_TOKENS")
        output_cost = self._get_float("ESTIMATED_OUTPUT_COST_PER_1K_TOKENS")
        
        return Config(
            openai_api_key=openai_api_key,
            api_base_url=api_base_url,
            model=model,
            api_timeout_seconds=api_timeout,
            input_folder=input_folder,
            output_folder=output_folder,
            image_extensions=image_extensions,
            batch_size=batch_size,
            max_concurrent_requests=max_concurrent,
            poll_interval_seconds=poll_interval,
            max_retries=max_retries,
            backoff_multiplier=backoff_mult,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            log_level=log_level,
            log_file=log_file,
            verbose_progress=verbose,
            state_file=state_file,
            error_log_file=error_log_file,
            auto_resume=auto_resume,
            track_costs=track_costs,
            estimated_input_cost_per_1k_tokens=input_cost,
            estimated_output_cost_per_1k_tokens=output_cost,
        )
    
    def _get_required(self, key: str) -> str:
        """Get required string value from config"""
        try:
            return self.parser.get("DEFAULT", key)
        except (configparser.NoOptionError, configparser.NoSectionError):
            raise ValueError(f"Required config value missing: {key}")
    
    def _get(self, key: str) -> str:
        """Get optional string value with default if available"""
        try:
            return self.parser.get("DEFAULT", key)
        except (configparser.NoOptionError, configparser.NoSectionError):
            if key in self.DEFAULTS:
                return self.DEFAULTS[key]
            raise ValueError(f"Required config value missing: {key}")
    
    def _get_int(self, key: str) -> int:
        """Get integer value from config"""
        try:
            return int(self._get(key))
        except ValueError:
            raise ValueError(f"Invalid integer value for {key}")
    
    def _get_float(self, key: str) -> float:
        """Get float value from config"""
        try:
            return float(self._get(key))
        except ValueError:
            raise ValueError(f"Invalid float value for {key}")
    
    def _get_bool(self, key: str) -> bool:
        """Get boolean value from config"""
        value = self._get(key).lower()
        if value in ["true", "yes", "1", "on"]:
            return True
        elif value in ["false", "no", "0", "off"]:
            return False
        else:
            raise ValueError(f"Invalid boolean value for {key}: {value}")
    
    def _get_path_required(self, key: str) -> Path:
        """Get required path from config"""
        path_str = self._get_required(key)
        path = Path(path_str).expanduser().resolve()
        return path


def load_config(config_path: Optional[str] = None) -> Config:
    """Convenience function to load config"""
    loader = ConfigLoader(config_path)
    return loader.load()
