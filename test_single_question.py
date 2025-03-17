#!/usr/bin/env python3
"""
Test script for the Spring Boot Analyzer's analyze comprehensive analysis.
This script tests the functionality of analyzing a Spring Boot application
using a single question for all three analysis types, with optional verification.
"""
import argparse
from spring_boot_analyzer.analyzer import QueryProcessor

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test the analyze comprehensive analysis feature")
    parser.add_argument("--no-verify", action="store_true", help="Skip self-verification step")
    parser.add_argument("--response-format", choices=["both", "original", "verification"], default="both", 
                       help="Which responses to show: both, original only, or verification only")
    args = parser.parse_args()
    
    # Initialize the processor
    processor = QueryProcessor(summary_dir="summary")
    
    # Define the single question
    question = "How can we implement recurring transfers and what would be the impact of adding a category field to transactions?"
    
    print("Processing comprehensive analysis with single question:")
    print(f"Question: {question}")
    
    # Get the response
    verify = not args.no_verify
    response = processor.analyze_comprehensive_single_question(question, verify=verify)
    
    # Handle response format
    if hasattr(args, 'response_format') and verify:
        if "## Original Response:" in response and "## Verification:" in response:
            if args.response_format == "original":
                # Extract only the original response
                original_part = response.split("## Verification:")[0].replace("## Original Response:", "").strip()
                print("\nANALYZE COMPREHENSIVE ANALYSIS RESPONSE (ORIGINAL ONLY):")
                print("=" * 80)
                print(original_part)
                print("=" * 80)
            elif args.response_format == "verification":
                # Extract only the verification
                verification_part = response.split("## Verification:")[1].strip()
                print("\nANALYZE COMPREHENSIVE ANALYSIS RESPONSE (VERIFICATION ONLY):")
                print("=" * 80)
                print(verification_part)
                print("=" * 80)
            else:
                # Show both (default)
                print("\nANALYZE COMPREHENSIVE ANALYSIS RESPONSE:")
                print("=" * 80)
                print(response)
                print("=" * 80)
        else:
            # If the response doesn't have the expected format, just print it as is
            print("\nANALYZE COMPREHENSIVE ANALYSIS RESPONSE:")
            print("=" * 80)
            print(response)
            print("=" * 80)
    else:
        # If no response format specified or verification is disabled, print as is
        print("\nANALYZE COMPREHENSIVE ANALYSIS RESPONSE:")
        print("=" * 80)
        print(response)
        print("=" * 80)

if __name__ == "__main__":
    main() 