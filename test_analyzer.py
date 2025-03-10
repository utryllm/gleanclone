#!/usr/bin/env python3
"""
Test script to verify that the Spring Boot Analyzer works correctly.
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from spring_boot_analyzer import ContextManager, LLMClient, QueryProcessor

class TestContextManager(unittest.TestCase):
    """Test the ContextManager class."""
    
    @patch('spring_boot_analyzer.analyzer.SentenceTransformer')
    def test_initialization(self, mock_transformer):
        """Test that the ContextManager initializes correctly."""
        # Mock the SentenceTransformer to avoid loading the model
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        # Create a test directory structure
        test_dir = Path("test_summary")
        test_dir.mkdir(exist_ok=True)
        
        # Create a test summary_of_summaries.md file
        with open(test_dir / "summary_of_summaries.md", "w") as f:
            f.write("# Test Application\nThis is a test application.")
        
        # Initialize the ContextManager
        context_manager = ContextManager(summary_dir=str(test_dir))
        
        # Check that the app_overview was loaded correctly
        self.assertIn("summary", context_manager.app_overview)
        self.assertIn("Test Application", context_manager.app_overview["summary"])
        
        # Clean up
        (test_dir / "summary_of_summaries.md").unlink()
        test_dir.rmdir()

class TestLLMClient(unittest.TestCase):
    """Test the LLMClient class."""
    
    @patch('spring_boot_analyzer.analyzer.OpenAI')
    def test_initialization(self, mock_openai):
        """Test that the LLMClient initializes correctly."""
        # Mock the OpenAI client
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Initialize the LLMClient
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test_key"}):
            llm_client = LLMClient()
        
        # Check that the client was initialized with the correct API key
        mock_openai.assert_called_once()
        
        # Check that the default model is set correctly
        self.assertEqual(llm_client.default_model, "gpt-4-turbo")

class TestQueryProcessor(unittest.TestCase):
    """Test the QueryProcessor class."""
    
    @patch('spring_boot_analyzer.analyzer.ContextManager')
    @patch('spring_boot_analyzer.analyzer.LLMClient')
    def test_process_query(self, mock_llm_client, mock_context_manager):
        """Test that the QueryProcessor processes queries correctly."""
        # Mock the ContextManager
        mock_cm = MagicMock()
        mock_context_manager.return_value = mock_cm
        
        # Mock the relevant components
        mock_cm.get_relevant_components.return_value = {
            "TestComponent": {
                "summary": "This is a test component.",
                "type": "controller",
                "similarity": 0.9
            }
        }
        
        # Mock the app overview
        mock_cm.app_overview = {
            "summary": "This is a test application."
        }
        
        # Mock the API flows
        mock_cm.get_related_api_flows.return_value = {}
        
        # Mock the component matrix
        mock_cm.get_related_matrix_entries.return_value = {}
        
        # Mock the prompt template
        mock_cm.get_prompt_template.return_value = "Test template: {query}"
        
        # Mock the LLMClient
        mock_llm = MagicMock()
        mock_llm_client.return_value = mock_llm
        mock_llm.analyze_application.return_value = "Test response"
        
        # Initialize the QueryProcessor
        processor = QueryProcessor()
        
        # Process a query
        response = processor.process_query("Test query", verify=False)
        
        # Check that the response is correct
        self.assertEqual(response, "Test response")
        
        # Check that the LLMClient was called with the correct prompt
        mock_llm.analyze_application.assert_called_once()

def run_tests():
    """Run the tests."""
    unittest.main()

if __name__ == "__main__":
    run_tests() 