#!/usr/bin/env python3
"""
Script to install the Spring Boot Analyzer package in development mode.
"""
import os
import sys
import subprocess

def main():
    """Install the package in development mode."""
    print("Installing Spring Boot Analyzer in development mode...")
    
    # Install the package in development mode
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], 
                           capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Installation successful!")
        print("\nYou can now use the package in your Python code:")
        print("from spring_boot_analyzer import QueryProcessor")
        print("\nOr run the CLI:")
        print("spring-boot-analyzer --help")
    else:
        print("Installation failed!")
        print(f"Error: {result.stderr}")
        
    return result.returncode

if __name__ == "__main__":
    sys.exit(main()) 