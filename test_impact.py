#!/usr/bin/env python3
"""
Test script for the Spring Boot Analyzer's impact analysis.
"""
from spring_boot_analyzer.analyzer import QueryProcessor

def main():
    # Initialize the processor
    processor = QueryProcessor(summary_dir="summary")
    
    # Process an impact analysis
    change_description = "Add a fraud check with OFAC system on withdraw flow"
    print(f"Processing impact analysis: {change_description}")
    
    # Get the response
    response = processor.analyze_code_change_impact(change_description)
    
    # Print the response
    print("\nIMPACT ANALYSIS RESPONSE:")
    print("=" * 80)
    print(response)
    print("=" * 80)

if __name__ == "__main__":
    main() 