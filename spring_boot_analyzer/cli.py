#!/usr/bin/env python3
import argparse
import sys
import logging
from .analyzer import QueryProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Spring Boot Application Analyzer")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Process a general query about the application")
    query_parser.add_argument("query_text", help="The query to process")
    query_parser.add_argument("--summary-dir", default="summary", help="Path to the summary directory")
    query_parser.add_argument("--no-verify", action="store_true", help="Skip self-verification step")
    
    # Feature implementation command
    feature_parser = subparsers.add_parser("feature", help="Analyze how to implement a new feature")
    feature_parser.add_argument("feature_description", help="Description of the feature to implement")
    feature_parser.add_argument("--summary-dir", default="summary", help="Path to the summary directory")
    feature_parser.add_argument("--no-verify", action="store_true", help="Skip self-verification step")
    
    # Impact analysis command
    impact_parser = subparsers.add_parser("impact", help="Analyze the impact of a code change")
    impact_parser.add_argument("change_description", help="Description of the code change")
    impact_parser.add_argument("--summary-dir", default="summary", help="Path to the summary directory")
    impact_parser.add_argument("--no-verify", action="store_true", help="Skip self-verification step")
    
    # Interactive mode command
    interactive_parser = subparsers.add_parser("interactive", help="Start interactive mode")
    interactive_parser.add_argument("--summary-dir", default="summary", help="Path to the summary directory")
    interactive_parser.add_argument("--no-verify", action="store_true", help="Skip self-verification step")
    
    # Demo command
    demo_parser = subparsers.add_parser("demo", help="Run a demo with example queries")
    demo_parser.add_argument("--summary-dir", default="summary", help="Path to the summary directory")
    demo_parser.add_argument("--no-verify", action="store_true", help="Skip self-verification step")
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command is provided, show help
    if not args.command:
        parser.print_help()
        return
    
    # Initialize the processor
    processor = QueryProcessor(summary_dir=args.summary_dir)
    verify = not args.no_verify if hasattr(args, 'no_verify') else True
    
    # Execute the appropriate command
    if args.command == "query":
        response = processor.process_query(args.query_text, verify=verify)
        print(f"\n{response}")
        
    elif args.command == "feature":
        response = processor.analyze_feature_implementation(args.feature_description)
        print(f"\n{response}")
        
    elif args.command == "impact":
        response = processor.analyze_code_change_impact(args.change_description)
        print(f"\n{response}")
        
    elif args.command == "interactive":
        run_interactive_mode(processor, verify)
        
    elif args.command == "demo":
        run_demo(processor, verify)

def run_interactive_mode(processor, verify):
    """Run the analyzer in interactive mode."""
    print("\n=== Spring Boot Application Analyzer Interactive Mode ===")
    print("Type 'exit' or 'quit' to end the session.")
    print("Type 'feature: <description>' to analyze feature implementation.")
    print("Type 'impact: <description>' to analyze code change impact.")
    print("Type any other text to process as a general query.\n")
    
    while True:
        try:
            user_input = input("\nEnter your query: ")
            
            if user_input.lower() in ["exit", "quit"]:
                print("Exiting interactive mode.")
                break
                
            if user_input.lower().startswith("feature: "):
                feature_desc = user_input[9:].strip()
                print("\nAnalyzing feature implementation...")
                response = processor.analyze_feature_implementation(feature_desc)
                
            elif user_input.lower().startswith("impact: "):
                change_desc = user_input[8:].strip()
                print("\nAnalyzing code change impact...")
                response = processor.analyze_code_change_impact(change_desc)
                
            else:
                print("\nProcessing query...")
                response = processor.process_query(user_input, verify=verify)
                
            print(f"\n{response}")
            
        except KeyboardInterrupt:
            print("\nExiting interactive mode.")
            break
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            print(f"\nError: {str(e)}")

def run_demo(processor, verify):
    """Run a demo with example queries."""
    print("\n=== Spring Boot Application Analyzer Demo ===\n")
    
    # Example queries
    queries = [
        "What is the overall architecture of this Spring Boot application?",
        "How does the transaction flow work in this application?",
        "What would be the impact of adding a new 'address' field to the User entity?",
        "How would I implement JWT authentication in this application?"
    ]
    
    # Process each query
    for query in queries:
        print(f"\n\n{'='*80}\nQUERY: {query}\n{'='*80}\n")
        print("Processing query...")
        response = processor.process_query(query, verify=verify)
        print(f"\nRESPONSE:\n{response}")
        
        # Pause between queries
        if query != queries[-1]:
            input("\nPress Enter to continue to the next query...")
    
    # Example feature implementation analysis
    feature = "Add a feature to allow users to set up recurring transfers between accounts"
    print(f"\n\n{'='*80}\nFEATURE IMPLEMENTATION: {feature}\n{'='*80}\n")
    print("Analyzing feature implementation...")
    response = processor.analyze_feature_implementation(feature)
    print(f"\nANALYSIS:\n{response}")
    
    input("\nPress Enter to continue...")
    
    # Example code change impact analysis
    change = "Change the Transaction entity to include a 'category' field for transaction categorization"
    print(f"\n\n{'='*80}\nCODE CHANGE IMPACT: {change}\n{'='*80}\n")
    print("Analyzing code change impact...")
    response = processor.analyze_code_change_impact(change)
    print(f"\nIMPACT ANALYSIS:\n{response}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        print(f"\nError: {str(e)}")
        sys.exit(1) 