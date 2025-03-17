# Running the Glean Code Analysis Tool

This guide provides instructions on how to run the Glean code analysis tool (`glean_code_ds.py`) for analyzing Spring Boot applications.

## Prerequisites

- Python 3.8 or higher
- Required Python packages:
  - javalang
  - git
  - tqdm
  - networkx
  - matplotlib
  - pydot
  - Pillow
  - openai
- OpenAI API key (for GPT-4 access)
- Git installed on your system
- Graphviz installed (for diagram generation)

## Basic Usage

### 1. Running the Main Script

```bash
python glean_code_ds.py [options]
```

Available options:
- `--force-clone`: Force clone repository even if it already exists
- `--force-summaries`: Force regenerate summaries even if they already exist
- `--skip-diagrams`: Skip generating diagrams
- `--skip-summaries`: Skip generating summaries
- `--llm-optimizations`: Generate LLM-optimized summaries and templates

### 2. Configuration

Before running the script, create a `config.json` file in the same directory with the following structure:

```json
{
    "repo_url": "https://github.com/your-repo-url",
    "clone_dir": "./gleanclone",
    "openai_api_key": "your-openai-api-key"
}
```

### 3. Example Commands

#### Basic Analysis
```bash
python glean_code_ds.py
```

#### Force Regenerate All
```bash
python glean_code_ds.py --force-clone --force-summaries
```

#### Skip Diagrams
```bash
python glean_code_ds.py --skip-diagrams
```

#### Generate LLM Optimizations
```bash
python glean_code_ds.py --llm-optimizations
```

## Output Files

The script generates several output files in different directories:

### 1. Code Index Directory (`code_index/`)
- `index.json`: Contains parsed code information
- `api_flow.json`: Contains API flow information
- `sequence_diagram.puml`: PlantUML sequence diagram
- `sequence_diagram.png`: Generated sequence diagram
- `c4_level1.png` through `c4_level4.png`: C4 model diagrams
- `api_flow.png`: API flow diagram

### 2. Summary Directory (`summary/`)
- `file_summaries/`: Contains summaries of individual Java files
- `module_summaries/`: Contains summaries of modules/packages
- `summary_of_summaries.md`: Comprehensive overview
- `component_relationship_matrix.md`: Component dependencies
- `enhanced_api_flow.json`: LLM-optimized API flow representation
- `llm_prompts/`: Contains generated prompt templates

## Features

### 1. Code Analysis
- Parses Java files
- Extracts API endpoints
- Analyzes dependencies
- Generates call graphs

### 2. Diagram Generation
- Sequence diagrams
- C4 model diagrams (4 levels)
- API flow diagrams
- Component relationship diagrams

### 3. Summary Generation
- File-level summaries
- Module-level summaries
- Application overview
- Component relationship matrix

### 4. LLM Optimizations
- Enhanced API flow representation
- Component relationship matrix
- LLM prompt templates

## Directory Structure

```
project/
├── glean_code_ds.py           # Main analysis script
├── config.json               # Configuration file
├── code_index/              # Code analysis output
│   ├── index.json
│   ├── api_flow.json
│   ├── sequence_diagram.puml
│   ├── sequence_diagram.png
│   ├── c4_level1.png
│   ├── c4_level2.png
│   ├── c4_level3.png
│   ├── c4_level4.png
│   └── api_flow.png
└── summary/                 # Summary output
    ├── file_summaries/
    ├── module_summaries/
    ├── summary_of_summaries.md
    ├── component_relationship_matrix.md
    ├── enhanced_api_flow.json
    └── llm_prompts/
```

## Troubleshooting

1. **Missing Dependencies**
   ```bash
   pip install javalang git tqdm networkx matplotlib pydot Pillow openai
   ```

2. **Graphviz Installation**
   - Windows: Download and install from https://graphviz.org/download/
   - Linux: `sudo apt-get install graphviz`
   - macOS: `brew install graphviz`

3. **Git Issues**
   - Ensure Git is installed and accessible from command line
   - Check repository URL is correct in config.json

4. **OpenAI API Issues**
   - Verify API key in config.json
   - Check API key permissions and quota

5. **File Permission Issues**
   - Ensure write permissions in output directories
   - Check file permissions for generated files

## Common Issues

1. **Repository Cloning Fails**
   - Check internet connection
   - Verify repository URL
   - Ensure Git is installed

2. **Diagram Generation Fails**
   - Verify Graphviz installation
   - Check file permissions
   - Ensure sufficient disk space

3. **Summary Generation Fails**
   - Check OpenAI API key
   - Verify file access permissions
   - Ensure sufficient memory

4. **Java Parsing Errors**
   - Check Java file encoding
   - Verify Java syntax
   - Ensure file is not corrupted

## Additional Resources

- See the code comments in `glean_code_ds.py` for detailed implementation information
- Check the generated documentation in the summary directory
- Review the component relationship matrix for dependency information 