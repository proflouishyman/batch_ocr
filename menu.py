"""
menu.py - Interactive CLI menu for processing mode selection
"""

from typing import List
import sys


class ProcessingMode:
    """Enum-like class for processing modes"""
    NEW_ONLY = "new_only"
    REPROCESS_ALL = "reprocess_all"
    RETRY_FAILED = "retry_failed"
    CONTINUE = "continue"
    EXIT = "exit"


class MenuHandler:
    """Handles interactive CLI menu"""
    
    @staticmethod
    def print_header():
        """Print menu header"""
        print("\n" + "=" * 60)
        print(" " * 15 + "OCR PROCESSOR - Main Menu")
        print("=" * 60 + "\n")
    
    @staticmethod
    def print_menu():
        """Print menu options"""
        print("What would you like to do?\n")
        print("1. Process new images only")
        print("   (Skip files already in processed_files.csv)")
        print()
        print("2. Reprocess everything")
        print("   (Reset state, process all images from scratch)")
        print()
        print("3. Retry failed files only")
        print("   (Only process files marked as ERROR)")
        print()
        print("4. Continue where we left off")
        print("   (Resume interrupted processing)")
        print()
        print("5. Exit")
        print()
    
    @staticmethod
    def get_user_choice() -> str:
        """Get user input and return processing mode"""
        while True:
            try:
                choice = input("Select option [1-5]: ").strip()
                
                if choice == "1":
                    return ProcessingMode.NEW_ONLY
                elif choice == "2":
                    return ProcessingMode.REPROCESS_ALL
                elif choice == "3":
                    return ProcessingMode.RETRY_FAILED
                elif choice == "4":
                    return ProcessingMode.CONTINUE
                elif choice == "5":
                    return ProcessingMode.EXIT
                else:
                    print("Invalid option. Please enter 1-5.")
            
            except KeyboardInterrupt:
                print("\nExiting...")
                sys.exit(0)
            except Exception as e:
                print(f"Error reading input: {e}")
    
    @staticmethod
    def show_menu() -> str:
        """Show full menu and return user's choice"""
        MenuHandler.print_header()
        MenuHandler.print_menu()
        return MenuHandler.get_user_choice()
    
    @staticmethod
    def confirm_action(message: str) -> bool:
        """Get yes/no confirmation from user"""
        while True:
            try:
                response = input(f"{message} (y/n): ").strip().lower()
                if response in ["y", "yes"]:
                    return True
                elif response in ["n", "no"]:
                    return False
                else:
                    print("Please enter 'y' or 'n'")
            except KeyboardInterrupt:
                print("\nCancelled")
                return False
    
    @staticmethod
    def print_mode_selected(mode: str):
        """Print confirmation of selected mode"""
        mode_descriptions = {
            ProcessingMode.NEW_ONLY: "Processing NEW images only (skipping processed files)",
            ProcessingMode.REPROCESS_ALL: "Reprocessing ALL images from scratch",
            ProcessingMode.RETRY_FAILED: "Retrying only FAILED files",
            ProcessingMode.CONTINUE: "Continuing from where we left off",
            ProcessingMode.EXIT: "Exiting"
        }
        
        description = mode_descriptions.get(mode, "Unknown mode")
        print(f"\n✓ {description}\n")
    
    @staticmethod
    def print_stats(stats: dict):
        """Print current statistics"""
        print("\nCurrent State:")
        print(f"  Total files processed: {stats['total']}")
        print(f"    ✓ Success: {stats['success']}")
        print(f"    ✗ Failed: {stats['error']}")
        print(f"    ⏱ Pending: {stats['pending']}")
        print(f"    ⊘ Skipped: {stats['skipped']}")
        print()
