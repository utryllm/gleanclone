# Technical Details: spring_boot_analyzer

## Architecture Overview

`spring_boot_analyzer` is a Python-based semantic code analysis and query system built on a modular architecture that leverages large language models (LLMs) for context-aware code understanding. It implements a retrieval-augmented generation (RAG) pattern to provide accurate responses about Spring Boot applications.

## Core Components

### 1. Context Manager
```python
class ContextManager:
    def __init__(self, summary_dir="summary"):
        # Initializes the context manager with the summary directory
```
- Responsible for loading and managing all code context information
- Implements vector embeddings for semantic search capabilities
- Manages file summaries, module summaries, API flows, and component relationships
- Provides context retrieval methods for query processing

### 2. LLM Client
```python
class LLMClient:
    def __init__(self):
        # Initializes the LLM client with API configuration
```
- Handles communication with OpenAI's API (or other LLM providers)
- Manages API key authentication and request formatting
- Implements configurable parameters (model, temperature, max_tokens)
- Provides error handling and retry logic for API calls

### 3. Query Processor
```python
class QueryProcessor:
    def __init__(self, summary_dir="summary"):
        # Initializes the query processor with context manager and LLM client
```
- Orchestrates the query processing pipeline
- Retrieves relevant context based on query semantics
- Constructs prompts with appropriate context
- Processes responses and performs self-verification

## Technical Implementation Details

### Vector Embedding and Semantic Search

```python
def _create_embeddings(self):
    # Creates embeddings for all summaries for similarity search
```
```python
def get_relevant_components(self, query, top_n=5):
    # Gets the most relevant components for a query using semantic similarity
```

- Uses `sentence-transformers` library with the `all-MiniLM-L6-v2` model
- Creates vector embeddings for all file and module summaries
- Implements cosine similarity for relevance ranking
- Returns top-N most relevant components with similarity scores

### Context Loading and Processing

```python
def _load_file_summaries(self):
    # Loads all file summaries from the file_summaries directory
```
```python
def _load_api_flows(self):
    # Loads the enhanced API flow representation
```
```python
def _load_component_matrix(self):
    # Loads the component relationship matrix
```
```python
def _load_prompt_templates(self):
    # Loads the LLM prompt templates
```

- Implements robust file loading with error handling
- Parses markdown and JSON formats into structured data
- Determines component types based on naming conventions and content
- Organizes loaded data for efficient retrieval

### Prompt Engineering

```python
def build_prompt(self, query, context, template_name="general_analysis_template"):
    # Builds a prompt using a template and context
```

- Uses template-based prompt construction
- Dynamically formats context data into templates
- Handles different template types for different query types
- Optimizes prompt structure for LLM comprehension

### Self-Verification System

```python
def _verify_response(self, response, context):
    # Verifies the response against the context for accuracy
```

- Implements a two-pass approach for response verification
- Checks for consistency with provided context
- Verifies component relationships and API flows
- Corrects inaccuracies in the original response

### Specialized Analysis Types

```python
def analyze_feature_implementation(self, feature_description):
    # Analyzes how a new feature would be implemented in the application
```
```python
def analyze_code_change_impact(self, change_description):
    # Analyzes the impact of a code change on the application
```

- Provides specialized processing for different query types
- Uses dedicated templates for each analysis type
- Implements domain-specific context retrieval strategies
- Returns structured analysis results

## Data Flow

1. **Query Intake**
   - User submits a natural language query
   - Query is processed to determine the type of analysis needed

2. **Context Retrieval**
   - Query is converted to vector embedding
   - Semantic search identifies relevant components
   - Related API flows and component relationships are retrieved

3. **Prompt Construction**
   - Appropriate template is selected based on query type
   - Context is formatted and inserted into template
   - Final prompt is constructed with query and context

4. **LLM Processing**
   - Prompt is sent to LLM API
   - Response is received from LLM
   - Initial response is parsed and structured

5. **Self-Verification**
   - Verification prompt is constructed with original response and context
   - Verification prompt is sent to LLM
   - Verified/corrected response is returned to user

## Command-Line Interface

```
usage: spring_boot_analyzer_cli.py [-h] {query,feature,impact,interactive,demo} ...

Spring Boot Application Analyzer

positional arguments:
  {query,feature,impact,interactive,demo}
                        Command to execute
    query               Process a general query about the application
    feature             Analyze how to implement a new feature
    impact              Analyze the impact of a code change
    interactive         Start interactive mode
    demo                Run a demo with example queries

options:
  -h, --help            show this help message and exit
```

## Environment Configuration

Configuration is managed through environment variables in a `.env` file:

```
# OpenAI API Key
OPENAI_API_KEY=your_api_key_here

# LLM Configuration
LLM_MODEL=gpt-4-turbo
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2000

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=spring_boot_analyzer.log
```

## Performance Considerations

1. **Embedding Caching**
   - Embeddings are computed once and cached in memory
   - Avoids redundant computation for repeated queries

2. **Context Optimization**
   - Only relevant context is included in prompts
   - Reduces token usage and improves response quality

3. **Parallel Processing**
   - Implements asynchronous API calls where appropriate
   - Uses threading for concurrent operations

## Security Considerations

1. **API Key Management**
   - Uses environment variables for sensitive credentials
   - Implements secure key handling practices

2. **Input Validation**
   - Sanitizes user input before processing
   - Prevents injection attacks in prompts

3. **Output Filtering**
   - Validates LLM responses before presenting to users
   - Removes potentially harmful content

## Integration Capabilities

1. **Library Usage**
   ```python
   from spring_boot_analyzer import QueryProcessor
   
   processor = QueryProcessor(summary_dir="path/to/summary")
   response = processor.process_query("How does authentication work?")
   ```

2. **IDE Integration**
   - Can be integrated with VS Code, IntelliJ, or other IDEs
   - Provides API for editor extensions

3. **CI/CD Pipeline Integration**
   - Can be used in automated documentation generation
   - Supports code review and analysis workflows

## Extensibility

1. **Custom Templates**
   - Add new templates in the `llm_prompts` directory
   - Define specialized templates for different query types

2. **Alternative Embedding Models**
   - Configurable embedding model selection
   - Support for different vector dimensions and similarity metrics

3. **Custom Analysis Types**
   - Extensible analysis framework
   - Add new analysis types by implementing the analysis interface 