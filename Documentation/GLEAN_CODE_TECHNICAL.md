# Technical Details: glean_code_ds.py

## Architecture Overview

`glean_code_ds.py` is a Python-based static code analysis tool specifically designed for Java Spring Boot applications. It employs a multi-stage pipeline architecture to extract, analyze, and synthesize information from codebases.

## Key Components

### 1. Repository Management
```python
def clone_repo(repo_url, clone_dir):
    # Clones or updates a Git repository
```
- Uses `gitpython` to handle repository operations
- Implements incremental updates to avoid redundant cloning
- Handles authentication for private repositories

### 2. Java Code Parser
```python
def parse_java_file(file_path):
    # Parses a Java file and extracts its structure
```
- Utilizes `javalang` for Java AST (Abstract Syntax Tree) parsing
- Extracts class definitions, methods, fields, and annotations
- Identifies Spring Boot specific components via annotation detection
- Maps inheritance relationships and dependency injection points

### 3. Incremental Indexing System
```python
def scan_directory_incremental(directory):
    # Scans a directory and indexes Java files incrementally
```
- Tracks file modification times using SHA-256 checksums
- Only processes files that have changed since the last run
- Maintains a persistent index using JSON serialization
- Implements parallel processing for performance optimization

### 4. API Endpoint Analyzer
```python
def extract_api_endpoints(tree):
    # Extracts REST API endpoints from a parsed Java file
```
```python
def extract_api_flow(tree, file_path):
    # Analyzes the flow of an API endpoint through the application
```
- Identifies REST controllers and their endpoints
- Maps request mappings to handler methods
- Traces method calls from controllers through services to repositories
- Builds a complete picture of API request handling

### 5. Diagram Generator
```python
def generate_sequence_diagram():
    # Generates sequence diagrams from the extracted API flows
```
```python
def generate_c4_diagrams():
    # Generates C4 architecture diagrams
```
```python
def generate_api_flow_diagram():
    # Generates API flow diagrams
```
- Uses PlantUML for sequence diagram generation
- Implements C4 model architecture visualization
- Creates GraphViz DOT files for dependency visualization
- Generates SVG and PNG outputs for documentation

### 6. Summary Generator
```python
def generate_file_summary(file_path):
    # Generates a summary for a single file
```
```python
def generate_module_summary(module_name, file_summaries):
    # Generates a summary for a module
```
```python
def generate_summary_of_summaries(module_summaries):
    # Generates an overall summary of the application
```
- Integrates with OpenAI's GPT models via API
- Implements prompt engineering for code summarization
- Uses a hierarchical approach: file → module → application
- Includes retry logic and error handling for API calls

### 7. LLM Optimization Components
```python
def generate_api_flow_for_llm(directory):
    # Generates an enhanced API flow representation for LLMs
```
```python
def generate_component_relationship_matrix():
    # Generates a component relationship matrix
```
```python
def generate_llm_prompt_templates():
    # Generates prompt templates for LLMs
```
- Creates structured JSON representations of API flows
- Builds dependency matrices for component relationships
- Designs specialized prompt templates for different analysis types
- Optimizes information format for LLM context windows

## Technical Implementation Details

### Data Structures

1. **Code Index**
   ```json
   {
     "classes": {
       "ClassName": {
         "file": "path/to/file.java",
         "methods": ["method1", "method2"],
         "fields": ["field1", "field2"],
         "annotations": ["@Controller", "@RequestMapping"],
         "extends": "ParentClass",
         "implements": ["Interface1", "Interface2"]
       }
     },
     "dependencies": {
       "ClassA": ["ClassB", "ClassC"],
       "ClassB": ["ClassD"]
     }
   }
   ```

2. **API Flow Representation**
   ```json
   {
     "/api/endpoint": {
       "method": "GET",
       "controller": {
         "class": "UserController",
         "method": "getUser",
         "file": "UserController.java"
       },
       "serviceChain": [
         {
           "class": "UserService",
           "method": "findById",
           "file": "UserService.java"
         }
       ],
       "repositoryAccess": [
         {
           "class": "UserRepository",
           "method": "findById",
           "file": "UserRepository.java"
         }
       ]
     }
   }
   ```

### Performance Optimizations

1. **Parallel Processing**
   - Uses `concurrent.futures.ProcessPoolExecutor` for multi-core utilization
   - Implements chunking for large codebases to manage memory usage

2. **Caching Mechanism**
   - Caches parsed ASTs to avoid redundant parsing
   - Implements LRU cache for frequently accessed components

3. **Incremental Processing**
   - Tracks file checksums to detect changes
   - Only regenerates affected summaries and diagrams

### Integration Points

1. **OpenAI API Integration**
   ```python
   def call_openai_api(prompt, max_retries=3, retry_delay=2):
       # Calls the OpenAI API with retry logic
   ```
   - Implements exponential backoff for rate limiting
   - Handles token limit constraints with chunking strategies
   - Manages API key authentication securely

2. **Visualization Tools**
   - PlantUML for sequence diagrams
   - GraphViz for dependency graphs
   - C4-PlantUML for architecture diagrams

## Command-Line Interface

```
usage: glean_code_ds.py [-h] [--force-regenerate] [--llm-optimizations]

options:
  -h, --help           show this help message and exit
  --force-regenerate   Force regeneration of all summaries
  --llm-optimizations  Generate LLM-optimized summaries and templates
```

## Configuration Options

Configuration is managed through a `config.json` file:

```json
{
  "repo_url": "https://github.com/username/repo.git",
  "clone_dir": "repo",
  "openai_model": "gpt-4-turbo",
  "max_tokens": 2000,
  "temperature": 0.2,
  "excluded_dirs": ["test", "target", "build"]
}
```

## Error Handling and Logging

- Implements structured logging with severity levels
- Provides detailed error messages for parsing failures
- Includes fallback mechanisms for API failures
- Logs performance metrics for optimization

## Extension Points

The system is designed for extensibility:

1. **Custom Analyzers**
   - Add new analysis functions by implementing the analyzer interface
   - Register custom analyzers in the pipeline

2. **Alternative LLM Providers**
   - Abstract API client allows swapping OpenAI with other providers
   - Configurable prompt templates for different LLM capabilities

3. **Additional Output Formats**
   - Extensible renderer system for different documentation formats
   - Support for custom visualization plugins 