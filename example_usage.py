#!/usr/bin/env python3
"""
Example script demonstrating how to use the Spring Boot Analyzer as a library.
"""
import os
from dotenv import load_dotenv
from spring_boot_analyzer import QueryProcessor

# Load environment variables from .env file
load_dotenv()

def main():
    # Initialize the processor
    processor = QueryProcessor(summary_dir="summary")
    
    print("Spring Boot Analyzer Example Usage\n")
    
    # Example 1: Basic query
    print("Example 1: Basic Query")
    print("---------------------")
    query = "What is the overall architecture of this Spring Boot application?"
    print(f"Query: {query}")
    response = processor.process_query(query)
    print(f"Response:\n{response}\n\n")
    
    # Example 2: Feature implementation analysis
    print("Example 2: Feature Implementation Analysis")
    print("----------------------------------------")
    feature = "Add a feature to allow users to set up recurring transfers between accounts"
    print(f"Feature: {feature}")
    response = processor.analyze_feature_implementation(feature)
    print(f"Analysis:\n{response}\n\n")
    
    # Example 3: Code change impact analysis
    print("Example 3: Code Change Impact Analysis")
    print("------------------------------------")
    change = "Change the Transaction entity to include a 'category' field for transaction categorization"
    print(f"Change: {change}")
    response = processor.analyze_code_change_impact(change)
    print(f"Impact Analysis:\n{response}\n\n")
    
    # Example 4: Custom query with specific template
    print("Example 4: Custom Query with Specific Template")
    print("--------------------------------------------")
    query = "How does authentication work in this application?"
    print(f"Query: {query}")
    response = processor.process_query(query, template_name="general_analysis_template", verify=True)
    print(f"Response:\n{response}\n\n")

if __name__ == "__main__":
    main() 