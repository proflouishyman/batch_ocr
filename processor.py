"""
processor.py - Main processing engine
Orchestrates image discovery, async processing, polling, and result persistence
"""

import asyncio
import json
import re
from pathlib import Path
from typing import List, Set, Optional, Dict, Any
from datetime import datetime

from config import Config
from logger import OCRLogger
from api_client import OpenAIClient, encode_image_to_base64
from validator import ResponseValidator
from state_manager import StateManager, ErrorLogger
from menu import MenuHandler, ProcessingMode


class OCRProcessor:
    """Main OCR processing engine"""
    
    def __init__(self, config: Config, logger: OCRLogger):
        self.config = config
        self.logger = logger
        self.state_manager = StateManager(config.state_file)
        self.error_logger = ErrorLogger(config.error_log_file)
        self.api_client = OpenAIClient(
            api_key=config.openai_api_key,
            base_url=config.api_base_url,
            model=config.model,
            timeout=config.api_timeout_seconds,
            max_retries=config.max_retries,
            backoff_multiplier=config.backoff_multiplier,
            logger=logger
        )
        log_path = Path(self.config.log_file).expanduser()
        if not log_path.is_absolute():
            log_path = Path.cwd() / log_path
        self.payload_dump_dir = log_path.parent / "payload_dumps"
        self.payload_dump_dir.mkdir(parents=True, exist_ok=True)
    
    def discover_images(self) -> List[Path]:
        """
        Discover image files in input folder
        
        Returns:
            List of Path objects for images
        """
        images = []
        
        try:
            for ext in self.config.image_extensions:
                # Search for files with this extension
                for image_path in self.config.input_folder.rglob(f"*{ext}"):
                    if image_path.is_file():
                        images.append(image_path)
        
        except Exception as e:
            self.logger.error(f"Error discovering images: {e}")
        
        return sorted(images)
    
    def filter_images_by_mode(self, images: List[Path], mode: str) -> List[Path]:
        """
        Filter images based on processing mode
        
        Args:
            images: List of discovered images
            mode: Processing mode
        
        Returns:
            Filtered list of images to process
        """
        if mode == ProcessingMode.REPROCESS_ALL:
            self.state_manager.clear()
            return images
        
        elif mode == ProcessingMode.NEW_ONLY:
            processed = self.state_manager.get_processed_files()
            return [img for img in images if img.name not in processed]
        
        elif mode == ProcessingMode.RETRY_FAILED:
            failed_files = set(self.state_manager.get_failed_files())
            return [img for img in images if img.name in failed_files]
        
        elif mode == ProcessingMode.CONTINUE:
            # Skip only completed (success or skipped), keep pending and errors
            processed = self.state_manager.get_processed_files()
            return [img for img in images if img.name not in processed]
        
        return images
    
    async def process_batch(self, images: List[Path]) -> Dict[str, Any]:
        """
        Process a batch of images
        
        Args:
            images: List of image paths to process
        
        Returns:
            Dictionary with processing results
        """
        results = {
            "processed": 0,
            "failed": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0
        }
        
        # Create tasks for all images in batch
        tasks = []
        for image_path in images:
            task = self._process_single_image(image_path)
            tasks.append(task)
        
        # Run tasks concurrently
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                results["failed"] += 1
                continue
            
            if result["success"]:
                results["processed"] += 1
                results["total_input_tokens"] += result.get("input_tokens", 0)
                results["total_output_tokens"] += result.get("output_tokens", 0)
                results["total_cost"] += result.get("cost", 0)
            else:
                results["failed"] += 1
        
        return results

    def _dump_raw_payload(
        self,
        filename: str,
        error_type: str,
        attempt: int,
        raw_payload: str
    ) -> Optional[Path]:
        """Write raw API payload to disk for debugging."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
            safe_stem = Path(filename).stem
            error_slug = re.sub(r"[^A-Za-z0-9_-]", "_", error_type or "unknown")
            dump_name = f"{safe_stem}_attempt{attempt}_{error_slug}_{timestamp}.txt"
            dump_path = self.payload_dump_dir / dump_name
            dump_path.write_text(raw_payload, encoding="utf-8", errors="replace")
            return dump_path
        except Exception as exc:
            self.logger.error(
                f"Failed to dump payload for {filename}: {exc}"
            )
            return None
    
    async def _process_single_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Process a single image
        
        Args:
            image_path: Path to image file
        
        Returns:
            Dictionary with processing result
        """
        filename = image_path.name
        output_path = self.config.output_folder / f"{image_path.stem}.json"
        
        try:
            # Skip if already processed
            if self.state_manager.is_processed(filename):
                self.logger.debug(f"Skipping already processed: {filename}")
                return {"success": False}
            
            # Encode image
            self.logger.debug(f"Encoding image: {filename}")
            try:
                image_base64 = encode_image_to_base64(str(image_path))
            except Exception as e:
                self.logger.error(f"Failed to encode {filename}: {e}")
                self.state_manager.mark_error(filename, f"Encoding failed: {e}")
                self.error_logger.log_error(filename, "encoding_error", str(e), can_retry=False)
                return {"success": False}
            
            # Mark as pending
            self.state_manager.mark_pending(filename)
            
            # Call API
            self.logger.debug(f"Submitting to API: {filename}")
            response = await self.api_client.process_image(
                image_base64=image_base64,
                system_prompt=self.config.system_prompt,
                user_prompt_template=self.config.user_prompt_template
            )
            
            # Handle API errors
            if not response.success:
                error_count = self.state_manager.get_file_error_count(filename) + 1
                can_retry = error_count < self.config.max_retries
                payload_path = None
                if response.raw_response:
                    payload_path = self._dump_raw_payload(
                        filename,
                        response.error_type or "unknown",
                        error_count,
                        response.raw_response
                    )

                log_message = f"API error for {filename} (attempt {error_count}): {response.error}"
                if payload_path:
                    log_message += f" | Payload saved to {payload_path}"
                self.logger.warning(log_message)
                error_notes = response.error
                if payload_path:
                    error_notes = f"{error_notes} | payload: {payload_path}"
                self.state_manager.mark_error(
                    filename, error_notes, response.request_id
                )
                self.error_logger.log_error(
                    filename, response.error_type or "unknown", response.error,
                    attempt=error_count, request_id=response.request_id or "",
                    can_retry=can_retry,
                    payload_path=str(payload_path) if payload_path else ""
                )

                return {"success": False}
            
            # Validate response
            is_valid, validation_errors = ResponseValidator.validate(response.data)
            
            if not is_valid:
                error_msg = "; ".join(validation_errors[:3])
                error_count = self.state_manager.get_file_error_count(filename) + 1
                
                self.logger.warning(
                    f"Validation failed for {filename} (attempt {error_count}): {error_msg}"
                )
                self.state_manager.mark_error(filename, error_msg, response.request_id)
                self.error_logger.log_error(
                    filename, "validation_failure", error_msg,
                    attempt=error_count, request_id=response.request_id or "",
                    can_retry=error_count < self.config.max_retries
                )
                
                return {"success": False}
            
            # Write output JSON
            try:
                output_data = {
                    "filename": filename,
                    "processing_timestamp": datetime.utcnow().isoformat() + "Z",
                    "api_request_id": response.request_id or "",
                    "tokens_used": {
                        "input": response.input_tokens,
                        "output": response.output_tokens,
                        "total": response.input_tokens + response.output_tokens
                    },
                    "estimated_cost": self.api_client.estimate_cost(
                        response.input_tokens,
                        response.output_tokens,
                        self.config.estimated_input_cost_per_1k_tokens,
                        self.config.estimated_output_cost_per_1k_tokens
                    ),
                    **response.data
                }
                
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                
                # Mark as success
                cost = output_data["estimated_cost"]
                self.state_manager.mark_success(
                    filename,
                    response.request_id or "",
                    response.input_tokens,
                    response.output_tokens
                )
                
                self.logger.info(f"✓ Processed: {filename}")
                
                return {
                    "success": True,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost": cost
                }
            
            except Exception as e:
                self.logger.error(f"Failed to write output for {filename}: {e}")
                self.state_manager.mark_error(filename, f"Output write failed: {e}")
                self.error_logger.log_error(
                    filename, "write_error", str(e), can_retry=False
                )
                return {"success": False}
        
        except Exception as e:
            self.logger.error(f"Unexpected error processing {filename}: {e}")
            self.state_manager.mark_error(filename, str(e))
            return {"success": False}
    
    async def run(self, mode: str):
        """
        Main processing loop
        
        Args:
            mode: Processing mode (from menu)
        """
        if mode == ProcessingMode.EXIT:
            self.logger.info("Exiting...")
            return
        
        self.logger.print_header("OCR Processor - Starting")
        
        # Discover images
        self.logger.info("Discovering images...")
        images = self.discover_images()
        self.logger.info(f"Found {len(images)} images")
        
        if len(images) == 0:
            self.logger.warning("No images found to process")
            return
        
        # Filter by mode
        filtered_images = self.filter_images_by_mode(images, mode)
        self.logger.info(f"Processing {len(filtered_images)} images ({mode})")
        
        if len(filtered_images) == 0:
            self.logger.info("No images to process")
            return
        
        # Initialize progress tracker
        self.logger.init_progress(len(filtered_images))
        
        # Process in batches
        batch_size = self.config.batch_size
        total_batches = (len(filtered_images) + batch_size - 1) // batch_size
        
        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(filtered_images))
            batch = filtered_images[start_idx:end_idx]
            
            self.logger.info(f"Processing batch {batch_num + 1}/{total_batches}")
            
            # Process batch
            batch_results = await self.process_batch(batch)
            
            # Update progress
            if self.logger.progress:
                for _ in range(batch_results["processed"]):
                    self.logger.progress.update(
                        success=True,
                        input_tokens=batch_results.get("total_input_tokens", 0) // max(1, batch_results["processed"]),
                        output_tokens=batch_results.get("total_output_tokens", 0) // max(1, batch_results["processed"]),
                        cost=batch_results.get("total_cost", 0) / max(1, batch_results["processed"])
                    )
                for _ in range(batch_results["failed"]):
                    self.logger.progress.update(success=False)
            
            # Print progress update
            self.logger.print_progress_update(
                batch_num + 1,
                total_batches,
                len(batch),
                batch_results["failed"]
            )
            
            # Save state after each batch
            self.state_manager.save_to_csv()
            self.error_logger.save_to_json()
        
        # Print summary
        self.logger.print_summary()
        
        # Print error summary if any
        error_summary = self.error_logger.get_error_summary()
        if error_summary:
            self.logger.info(f"\nError Summary: {error_summary}")


async def main():
    """Main entry point"""
    try:
        # Load config
        from config import load_config
        config = load_config()
        
        # Setup logger
        logger = OCRLogger(config.log_file, config.log_level, config.verbose_progress)
        
        # Show menu
        mode = MenuHandler.show_menu()
        MenuHandler.print_mode_selected(mode)
        
        # Show current stats
        state_manager = StateManager(config.state_file)
        stats = state_manager.get_stats()
        MenuHandler.print_stats(stats)
        
        # Confirm if reprocessing
        if mode == ProcessingMode.REPROCESS_ALL:
            if not MenuHandler.confirm_action("This will reset all progress. Continue?"):
                logger.info("Cancelled")
                return
        
        # Create processor and run
        processor = OCRProcessor(config, logger)
        await processor.run(mode)
    
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
