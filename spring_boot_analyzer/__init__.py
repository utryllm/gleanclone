"""
Spring Boot Application Analyzer

A tool for analyzing Spring Boot applications using LLMs with context-aware prompting.
"""

from .analyzer import ContextManager, LLMClient, QueryProcessor

__version__ = "0.1.0"
__all__ = ["ContextManager", "LLMClient", "QueryProcessor"] 