#!/usr/bin/env python3
"""
Simple test script for the Spring Boot Analyzer.
"""
from spring_boot_analyzer.analyzer import QueryProcessor

def main():
    # Initialize the processor
    processor = QueryProcessor(summary_dir="summary")
    
    # Process a query
    query = "Does this application use Meta's Glean algorithm?"
    print(f"Processing query: {query}")
    
    # Get the response
    response = processor.process_query(query)
    
    # Print the response
    print("\nCOMBINED RESPONSE (Original + Verification):")
    print("=" * 80)
    print(response)
    print("=" * 80)

if __name__ == "__main__":
    main() 