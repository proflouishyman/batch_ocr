"""
validator.py - Response validation and schema checking
Validates JSON responses from GPT API against expected schema
"""

from typing import Dict, Any, Tuple, List
import json


class ResponseValidator:
    """Validates OCR processor responses"""
    
    # Expected NER categories
    EXPECTED_NER_TYPES = [
        "PERSON", "ORG", "GPE", "DATE", "MONEY", "PERCENT", 
        "FACILITY", "PRODUCT", "EVENT"
    ]
    
    @staticmethod
    def validate(response_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate complete response structure
        
        Args:
            response_data: JSON response from API
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        # Check required top-level fields
        required_fields = ["raw_ocr", "corrected_ocr", "ner", "categories"]
        for field in required_fields:
            if field not in response_data:
                errors.append(f"Missing required field: {field}")
        
        if errors:
            return False, errors
        
        # Validate raw_ocr
        if not isinstance(response_data.get("raw_ocr"), str):
            errors.append("raw_ocr must be a string")
        elif len(response_data["raw_ocr"].strip()) == 0:
            errors.append("raw_ocr cannot be empty")
        
        # Validate corrected_ocr
        if not isinstance(response_data.get("corrected_ocr"), str):
            errors.append("corrected_ocr must be a string")
        elif len(response_data["corrected_ocr"].strip()) == 0:
            errors.append("corrected_ocr cannot be empty")
        
        # Validate NER structure
        ner_data = response_data.get("ner")
        if not isinstance(ner_data, dict):
            errors.append("ner must be an object/dict")
        else:
            # Check that NER values are lists
            for ner_type, values in ner_data.items():
                if not isinstance(values, list):
                    errors.append(f"ner.{ner_type} must be a list")
                else:
                    # Check that list contains strings
                    for i, val in enumerate(values):
                        if not isinstance(val, str):
                            errors.append(f"ner.{ner_type}[{i}] must be a string")
        
        # Validate categories structure
        categories = response_data.get("categories")
        if not isinstance(categories, dict):
            errors.append("categories must be an object/dict")
        else:
            required_category_fields = [
                "document_type", "confidence", "language", 
                "has_tables", "has_images", "page_count", "quality_score"
            ]
            
            for field in required_category_fields:
                if field not in categories:
                    errors.append(f"Missing required category field: {field}")
            
            # Type validation for categories
            if "confidence" in categories:
                try:
                    conf = float(categories["confidence"])
                    if not (0.0 <= conf <= 1.0):
                        errors.append("confidence must be between 0.0 and 1.0")
                except (ValueError, TypeError):
                    errors.append("confidence must be a number")
            
            if "quality_score" in categories:
                try:
                    score = float(categories["quality_score"])
                    if not (0 <= score <= 100):
                        errors.append("quality_score must be between 0 and 100")
                except (ValueError, TypeError):
                    errors.append("quality_score must be a number")
            
            if "page_count" in categories:
                try:
                    pages = int(categories["page_count"])
                    if pages < 1:
                        errors.append("page_count must be >= 1")
                except (ValueError, TypeError):
                    errors.append("page_count must be an integer")
            
            bool_fields = ["has_tables", "has_images"]
            for field in bool_fields:
                if field in categories:
                    if not isinstance(categories[field], bool):
                        errors.append(f"{field} must be a boolean")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def validate_partial(response_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Lenient validation - checks only critical fields
        Used for retry decisions
        
        Args:
            response_data: JSON response from API
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        # Absolutely required fields
        critical_fields = ["raw_ocr", "corrected_ocr"]
        for field in critical_fields:
            if field not in response_data:
                errors.append(f"Missing critical field: {field}")
                continue
            
            if not isinstance(response_data[field], str):
                errors.append(f"{field} must be a string")
            elif len(str(response_data[field]).strip()) == 0:
                errors.append(f"{field} cannot be empty")
        
        return len(errors) == 0, errors


class SchemaBuilder:
    """Helpers for building JSON schema for responses"""
    
    @staticmethod
    def get_json_schema() -> Dict[str, Any]:
        """Get the full JSON schema for responses"""
        return {
            "type": "object",
            "properties": {
                "raw_ocr": {
                    "type": "string",
                    "description": "Verbatim OCR output from the document"
                },
                "corrected_ocr": {
                    "type": "string",
                    "description": "Grammatically corrected and cleaned OCR text"
                },
                "ner": {
                    "type": "object",
                    "properties": {
                        "PERSON": {"type": "array", "items": {"type": "string"}},
                        "ORG": {"type": "array", "items": {"type": "string"}},
                        "GPE": {"type": "array", "items": {"type": "string"}},
                        "DATE": {"type": "array", "items": {"type": "string"}},
                        "MONEY": {"type": "array", "items": {"type": "string"}},
                        "PERCENT": {"type": "array", "items": {"type": "string"}},
                        "FACILITY": {"type": "array", "items": {"type": "string"}},
                        "PRODUCT": {"type": "array", "items": {"type": "string"}},
                        "EVENT": {"type": "array", "items": {"type": "string"}},
                    },
                    "description": "Named Entity Recognition results"
                },
                "categories": {
                    "type": "object",
                    "properties": {
                        "document_type": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "language": {"type": "string"},
                        "has_tables": {"type": "boolean"},
                        "has_images": {"type": "boolean"},
                        "page_count": {"type": "integer", "minimum": 1},
                        "quality_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    },
                    "required": [
                        "document_type", "confidence", "language",
                        "has_tables", "has_images", "page_count", "quality_score"
                    ],
                    "description": "Document classification and metadata"
                }
            },
            "required": ["raw_ocr", "corrected_ocr", "ner", "categories"]
        }
