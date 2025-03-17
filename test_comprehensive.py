#!/usr/bin/env python3
"""
Test script for the Spring Boot Analyzer's comprehensive analysis.
"""
from spring_boot_analyzer.analyzer import QueryProcessor

def main():
    # Initialize the processor
    processor = QueryProcessor(summary_dir="summary")
    
    # Define the analysis components
    query = "How does the transaction flow work in this application?"
    feature = "Add a feature to allow users to set up recurring transfers between accounts"
    change = "Change the Transaction entity to include a 'category' field for transaction categorization"
    
    print("Processing comprehensive analysis with:")
    print(f"Query: {query}")
    print(f"Feature: {feature}")
    print(f"Change: {change}")
    
    # Get the response
    response = processor.analyze_comprehensive(query, feature, change)
    
    # Print the response
    print("\nCOMPREHENSIVE ANALYSIS RESPONSE:")
    print("=" * 80)
    print(response)
    print("=" * 80)

if __name__ == "__main__":
    main() 