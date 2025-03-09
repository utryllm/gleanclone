import os
import json
import javalang
import git
import hashlib
import logging
import concurrent.futures
from tqdm import tqdm
from collections import defaultdict
import networkx as nx
import subprocess
import stat
import matplotlib.pyplot as plt
import pydot
from PIL import Image
import re
import openai
import time
from pathlib import Path
import argparse

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

INDEX_DIR = "code_index"
MOD_TIMES_FILE = "file_mod_times.json"
CONFIG_FILE = "config.json"
GRAPH_FILE = "dependency_graph.dot"
INDEX_JSON = os.path.join(INDEX_DIR, "index.json")
API_FLOW_JSON = os.path.join(INDEX_DIR, "api_flow.json")
SEQUENCE_DIAGRAM_FILE = os.path.join(INDEX_DIR, "sequence_diagram.puml")

# Summary directories and files
SUMMARY_DIR = "summary"
FILE_SUMMARIES_DIR = os.path.join(SUMMARY_DIR, "file_summaries")
MODULE_SUMMARIES_DIR = os.path.join(SUMMARY_DIR, "module_summaries")
SUMMARY_OF_SUMMARIES_FILE = os.path.join(SUMMARY_DIR, "summary_of_summaries.md")
PROMPTS_DIR = "prompts"

# Common Java framework packages to filter out
EXTERNAL_PACKAGES = {
    'org.springframework', 'javax', 'java', 'org.hibernate', 'org.junit',
    'org.mockito', 'org.apache', 'com.fasterxml', 'io.swagger', 'lombok',
    'jakarta', 'org.slf4j', 'ch.qos.logback', 'org.json', 'com.google',
    'org.testng', 'junit', 'org.junit.jupiter', 'org.junit.jupiter.api'
}

# Spring Boot specific annotations
SPRING_ANNOTATIONS = {
    '@RestController', '@Controller', '@Service', '@Repository', '@Component',
    '@Autowired', '@Value', '@Configuration', '@Bean', '@RequestMapping',
    '@GetMapping', '@PostMapping', '@PutMapping', '@DeleteMapping', '@PatchMapping'
}

# Test-related keywords to filter out
TEST_KEYWORDS = {
    'Test', 'Tests', 'TestCase', 'TestSuite', 'IntegrationTest', 
    'UnitTest', 'Spec', 'Specification', 'IT', 'E2E'
}

def is_test_class(class_name, file_path):
    # Check if class name contains test keywords
    if any(keyword in class_name for keyword in TEST_KEYWORDS):
        return True
    
    # Check if file path contains test-related directories
    test_dirs = {'test', 'tests', 'testing', 'it', 'e2e'}
    path_parts = file_path.lower().split(os.sep)
    return any(test_dir in path_parts for test_dir in test_dirs)

def is_external_dependency(dependency):
    return any(dependency.startswith(pkg) for pkg in EXTERNAL_PACKAGES)

def get_package_name(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = javalang.parse.parse(f.read())
            for path, node in tree:
                if isinstance(node, javalang.tree.PackageDeclaration):
                    return node.name
    except:
        pass
    return "default"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


CONFIG = load_config()


def clone_repo(repo_url, clone_dir):
    try:
        if os.path.exists(clone_dir):
            # Check if it's a git repository
            if os.path.exists(os.path.join(clone_dir, '.git')):
                logging.info(f"Repository already exists at {clone_dir}. Skipping clone.")
                return
            else:
                logging.warning(f"Directory {clone_dir} exists but is not a git repository. Deleting and re-cloning...")
                import shutil
                shutil.rmtree(clone_dir)

        logging.info(f"Cloning repository {repo_url} into {clone_dir}...")
        git.Repo.clone_from(repo_url, clone_dir)
        logging.info("Repository cloned successfully!")

        # ✅ Ensure `cloned_repo/` has full read/write/execute permissions
        os.chmod(clone_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)

        # ✅ Recursively set permissions for all files and directories
        for root, dirs, files in os.walk(clone_dir):
            for dir_name in dirs:
                os.chmod(os.path.join(root, dir_name), stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            for file_name in files:
                os.chmod(os.path.join(root, file_name),
                         stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)

        logging.info(f"Permissions set for {clone_dir} to allow read & write access.")

    except git.exc.GitError as e:
        logging.error(f"Error cloning repository: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while setting permissions: {e}")


def initialize_index():
    os.makedirs(INDEX_DIR, exist_ok=True)
    if not os.path.exists(INDEX_JSON) or os.stat(INDEX_JSON).st_size == 0:
        logging.warning(f"{INDEX_JSON} was missing or empty. Initializing with an empty dictionary.")
        save_to_file(INDEX_JSON, {})


def save_to_file(file_name, data):
    # ✅ Fix: Avoid duplicate paths
    file_path = file_name if os.path.isabs(file_name) else os.path.join(INDEX_DIR, os.path.basename(file_name))

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # ✅ Ensure directory exists
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        logging.info(f"File saved: {file_path}")  # ✅ Log file path
    except IOError as e:
        logging.error(f"Error saving to file {file_path}: {e}")


def load_from_file(file_name):
    # ✅ Fix: Ensure correct file path
    file_path = file_name if os.path.isabs(file_name) else os.path.join(INDEX_DIR, os.path.basename(file_name))

    try:
        if os.path.exists(file_path):
            if os.stat(file_path).st_size == 0:  # ✅ Handle empty files
                logging.warning(f"File {file_path} is empty. Returning empty dictionary.")
                return {}
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logging.warning(f"File {file_path} does not exist. Returning empty dictionary.")
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error loading file {file_path}: {e}")
    return {}


def extract_api_endpoints(tree):
    endpoints = []
    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            class_annotations = [ann.name for ann in node.annotations]
            base_path = ""
            
            # Check for @RequestMapping at class level
            for ann in node.annotations:
                if ann.name == 'RequestMapping':
                    if hasattr(ann, 'element') and ann.element:
                        for elem in ann.element:
                            if isinstance(elem, tuple) and len(elem) == 2:
                                name, value = elem
                                if name == 'value':
                                    base_path = value.value.strip('"')
                                    break
            
            # Check for @RestController or @Controller
            if any(ann in class_annotations for ann in ['RestController', 'Controller']):
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration):
                        method_annotations = [ann.name for ann in member.annotations]
                        http_method = None
                        path = ""
                        
                        # Check for HTTP method annotations
                        for ann in member.annotations:
                            if ann.name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'PatchMapping']:
                                http_method = ann.name.replace('Mapping', '').upper()
                                if hasattr(ann, 'element') and ann.element:
                                    for elem in ann.element:
                                        if isinstance(elem, tuple) and len(elem) == 2:
                                            name, value = elem
                                            if name == 'value':
                                                path = value.value.strip('"')
                                                break
                                break
                        
                        if http_method:
                            full_path = f"{base_path}/{path}".replace("//", "/")
                            endpoints.append({
                                "method": http_method,
                                "path": full_path,
                                "class": node.name,
                                "method_name": member.name,
                                "line_number": member.position.line
                            })
    return endpoints

def extract_api_flow(tree, file_path):
    """Extract API flow including service and repository dependencies."""
    api_flow = {
        "endpoints": [],
        "service_calls": [],
        "repository_calls": []
    }
    
    current_class = None
    current_method = None
    
    # Read the file content to extract annotation values directly
    with open(file_path, 'r', encoding='utf-8') as f:
        file_content = f.read()
    
    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            current_class = node.name
            class_annotations = [ann.name for ann in node.annotations]
            
            # Check for Spring annotations
            is_controller = any(ann in class_annotations for ann in ['RestController', 'Controller'])
            is_service = any(ann in class_annotations for ann in ['Service'])
            is_repository = any(ann in class_annotations for ann in ['Repository'])
            
            base_path = ""
            for ann in node.annotations:
                if ann.name == 'RequestMapping':
                    if hasattr(ann, 'element') and ann.element:
                        for elem in ann.element:
                            if isinstance(elem, tuple) and len(elem) == 2:
                                name, value = elem
                                if name == 'value':
                                    base_path = value.value.strip('"')
                                    break
            
            if is_controller:
                for member in node.body:
                    if isinstance(member, javalang.tree.MethodDeclaration):
                        current_method = member.name
                        method_annotations = [ann.name for ann in member.annotations]
                        http_method = None
                        endpoint_path = ""
                        
                        # Check for HTTP method annotations
                        for ann in member.annotations:
                            if ann.name in ['GetMapping', 'PostMapping', 'PutMapping', 'DeleteMapping', 'PatchMapping']:
                                http_method = ann.name.replace('Mapping', '').upper()
                                
                                # Extract path using regex
                                if member.position:
                                    line_number = member.position.line
                                    # Get a few lines before the method declaration to find the annotation
                                    lines = file_content.split('\n')
                                    for i in range(max(0, line_number - 10), line_number):
                                        if ann.name in lines[i]:
                                            # Extract path from annotation
                                            match = re.search(r'value\s*=\s*"([^"]*)"', lines[i])
                                            if match:
                                                endpoint_path = match.group(1)
                                            break
                                break
                        
                        if http_method:
                            api_flow["endpoints"].append({
                                "method": current_method,
                                "path": endpoint_path,
                                "class": current_class,
                                "line_number": member.position.line,
                                "http_method": http_method
                            })
            
            # Track service and repository dependencies
            for member in node.body:
                if isinstance(member, javalang.tree.FieldDeclaration):
                    for var in member.declarators:
                        field_type = member.type.name
                        if 'Service' in field_type:
                            api_flow["service_calls"].append({
                                "class": current_class,
                                "service": field_type,
                                "field": var.name
                            })
                        elif 'Repository' in field_type:
                            api_flow["repository_calls"].append({
                                "class": current_class,
                                "repository": field_type,
                                "field": var.name
                            })
    
    return api_flow

def parse_java_file(file_path):
    logging.info(f"Parsing Java file: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = javalang.parse.parse(f.read())
    except (javalang.parser.JavaSyntaxError, FileNotFoundError, IOError) as e:
        error_message = f"Error parsing Java file {file_path}: {e}"
        logging.error(error_message)
        return error_message

    index_data = load_from_file(INDEX_JSON)
    package_name = get_package_name(file_path)

    parsed_data = {
        "package": package_name,
        "classes": [], 
        "methods": [], 
        "fields": [], 
        "dependencies": [],
        "call_graph": [], 
        "inheritance": [], 
        "annotations": [], 
        "references": [],
        "api_flow": extract_api_flow(tree, file_path)
    }

    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            if not is_test_class(node.name, file_path):
                parsed_data["classes"].append({
                    "name": node.name,
                    "line_number": node.position.line,
                    "package": package_name,
                    "annotations": [ann.name for ann in node.annotations]
                })
        elif isinstance(node, javalang.tree.MethodDeclaration):
            if not any(keyword in node.name for keyword in TEST_KEYWORDS):
                parsed_data["methods"].append({
                    "name": node.name,
                    "line_number": node.position.line,
                    "annotations": [ann.name for ann in node.annotations]
                })
        elif isinstance(node, javalang.tree.Import):
            if not is_external_dependency(node.path):
                parsed_data["dependencies"].append(node.path)

    index_data[file_path] = parsed_data
    save_to_file(INDEX_JSON, index_data)

    # Save API flow data
    api_flow_data = load_from_file(API_FLOW_JSON)
    # Clear existing data to avoid duplicates
    api_flow_data = {}

    # Group endpoints by their full path
    for file_path, data in index_data.items():
        for endpoint in data.get("api_flow", {}).get("endpoints", []):
            base_path = ""
            # Find the base path from class annotations
            for class_info in data.get("classes", []):
                if class_info["name"] == endpoint["class"]:
                    for ann in class_info.get("annotations", []):
                        if "RequestMapping" in ann:
                            # Extract base path from RequestMapping
                            # This is a simplification - in a real implementation, you'd need to parse the annotation value
                            base_path = "api/v1"  # Default for this project
                            break
            
            full_path = f"{base_path}/{endpoint['path']}".replace("//", "/")
            
            if full_path not in api_flow_data:
                api_flow_data[full_path] = {
                    "endpoints": [],
                    "service_calls": []
                }
            
            api_flow_data[full_path]["endpoints"].append({
                "method": endpoint["method"],
                "path": endpoint["path"],
                "class": endpoint["class"],
                "line_number": endpoint["line_number"],
                "http_method": endpoint.get("http_method", "")
            })
            
            # Add service calls for this endpoint's controller
            for service_call in data.get("api_flow", {}).get("service_calls", []):
                if service_call["class"] == endpoint["class"]:
                    # Check if this service call is already added
                    service_already_added = False
                    for existing_service in api_flow_data[full_path].get("service_calls", []):
                        if (existing_service["class"] == service_call["class"] and 
                            existing_service["service"] == service_call["service"] and
                            existing_service["field"] == service_call["field"]):
                            service_already_added = True
                            break
                    
                    if not service_already_added:
                        api_flow_data[full_path]["service_calls"].append(service_call)

    save_to_file(API_FLOW_JSON, api_flow_data)

    return f"Successfully parsed {file_path}"


def generate_sequence_diagram():
    index_data = load_from_file(INDEX_JSON)

    if not index_data:
        logging.warning("No data found in index.json. Skipping sequence diagram generation.")
        return

    diagram_file = os.path.join(INDEX_DIR, "sequence_diagram.png")  # ✅ Save as PNG
    graph = pydot.Dot(graph_type='digraph', bgcolor="white")

    for file_path, data in index_data.items():
        caller_class = os.path.basename(file_path).replace(".java", "")

        for call in data.get("call_graph", []):
            callee_method = call["callee"]

            # ✅ Add nodes and edges
            caller_node = pydot.Node(caller_class, shape="rectangle", style="filled", fillcolor="lightblue")
            callee_node = pydot.Node(callee_method, shape="ellipse", style="filled", fillcolor="lightgreen")

            graph.add_node(caller_node)
            graph.add_node(callee_node)
            graph.add_edge(pydot.Edge(caller_node, callee_node, label="calls"))

    # ✅ Save as PNG
    graph.write_png(diagram_file)
    logging.info(f"Sequence diagram saved as {diagram_file}")

    # ✅ Display the PNG (Optional)
    img = Image.open(diagram_file)
    img.show()


def generate_c4_diagrams():
    """Generates all four levels of C4 diagrams."""
    index_data = load_from_file(INDEX_JSON)

    if not index_data:
        logging.warning("No data found in index.json. Skipping C4 diagram generation.")
        return

    # Level 1: System Context Diagram
    context_diagram = pydot.Dot(graph_type="digraph", bgcolor="white", 
                              label="Level 1: System Context Diagram", fontsize="20", labelloc="t")
    
    # Add main system node
    system_node = pydot.Node("Main System", shape="rectangle", style="filled", fillcolor="lightblue")
    context_diagram.add_node(system_node)
    
    # Add external actors
    actors = ["User", "Database", "External Service"]
    for actor in actors:
        actor_node = pydot.Node(actor, shape="person", style="filled", fillcolor="lightgreen")
        context_diagram.add_node(actor_node)
        context_diagram.add_edge(pydot.Edge(actor_node, system_node, label="interacts with"))
    
    context_diagram.write_png(os.path.join(INDEX_DIR, "c4_level1.png"))

    # Level 2: Container Diagram
    container_diagram = pydot.Dot(graph_type="digraph", bgcolor="white",
                                label="Level 2: Container Diagram", fontsize="20", labelloc="t")
    
    # Group containers by type
    containers = defaultdict(list)
    for file_path, data in index_data.items():
        if "Controller" in file_path:
            containers["Web Controllers"].append(data["package"])
        elif "Service" in file_path:
            containers["Services"].append(data["package"])
        elif "Repository" in file_path:
            containers["Repositories"].append(data["package"])
    
    # Add container nodes
    for container_type, packages in containers.items():
        container_node = pydot.Node(container_type, shape="rectangle", style="filled", fillcolor="lightblue")
        container_diagram.add_node(container_node)
        
        for package in packages:
            package_node = pydot.Node(package, shape="rectangle", style="filled", fillcolor="lightgreen")
            container_diagram.add_node(package_node)
            container_diagram.add_edge(pydot.Edge(container_node, package_node, label="contains"))
    
    container_diagram.write_png(os.path.join(INDEX_DIR, "c4_level2.png"))

    # Level 3: Component Diagram
    component_diagram = pydot.Dot(graph_type="digraph", bgcolor="white",
                                label="Level 3: Component Diagram", fontsize="20", labelloc="t")
    
    # Add components based on classes
    for file_path, data in index_data.items():
        for class_info in data["classes"]:
            class_node = pydot.Node(class_info["name"], shape="rectangle", style="filled", fillcolor="lightblue")
            component_diagram.add_node(class_node)
            
            # Add dependencies between components
            for dep in data["dependencies"]:
                dep_name = dep.split(".")[-1]
                if dep_name not in EXTERNAL_PACKAGES:
                    dep_node = pydot.Node(dep_name, shape="rectangle", style="filled", fillcolor="lightgreen")
                    component_diagram.add_node(dep_node)
                    component_diagram.add_edge(pydot.Edge(class_node, dep_node, label="depends on"))
    
    component_diagram.write_png(os.path.join(INDEX_DIR, "c4_level3.png"))

    # Level 4: Code Diagram
    code_diagram = pydot.Dot(graph_type="digraph", bgcolor="white",
                           label="Level 4: Code Diagram", fontsize="20", labelloc="t")
    
    # Add detailed method-level relationships
    for file_path, data in index_data.items():
        class_name = os.path.basename(file_path).replace(".java", "")
        class_node = pydot.Node(class_name, shape="rectangle", style="filled", fillcolor="lightblue")
        code_diagram.add_node(class_node)
        
        for method in data["methods"]:
            method_node = pydot.Node(f"{class_name}.{method['name']}", 
                                   shape="ellipse", style="filled", fillcolor="lightgreen")
            code_diagram.add_node(method_node)
            code_diagram.add_edge(pydot.Edge(class_node, method_node, label="contains"))
    
    code_diagram.write_png(os.path.join(INDEX_DIR, "c4_level4.png"))

    # Display all diagrams
    for level in range(1, 5):
        img = Image.open(os.path.join(INDEX_DIR, f"c4_level{level}.png"))
        img.show()


def generate_api_flow_diagram():
    """Generates a diagram showing the API flow and relationships."""
    index_data = load_from_file(INDEX_JSON)
    
    if not index_data:
        logging.warning("No data found in index.json. Skipping API flow diagram generation.")
        return

    diagram = pydot.Dot(graph_type="digraph", bgcolor="white",
                       label="API Flow Diagram", fontsize="20", labelloc="t")
    
    # Create nodes for controllers, services, and repositories
    controllers = set()
    services = set()
    repositories = set()
    
    # First pass: collect all components
    for file_path, data in index_data.items():
        for class_info in data["classes"]:
            annotations = class_info["annotations"]
            if any(ann in annotations for ann in ['RestController', 'Controller']):
                controllers.add(class_info["name"])
            elif 'Service' in annotations:
                services.add(class_info["name"])
            elif 'Repository' in annotations:
                repositories.add(class_info["name"])
    
    # Second pass: create nodes and edges
    for file_path, data in index_data.items():
        api_flow = data.get("api_flow", {})
        
        # Add controller nodes and their endpoints
        for endpoint in api_flow.get("endpoints", []):
            controller = endpoint["class"]
            if controller in controllers:
                controller_node = pydot.Node(controller, shape="rectangle", style="filled", fillcolor="lightblue")
                diagram.add_node(controller_node)
                
                endpoint_node = pydot.Node(f"{endpoint['method']} {endpoint['path']}", 
                                         shape="ellipse", style="filled", fillcolor="lightgreen")
                diagram.add_node(endpoint_node)
                diagram.add_edge(pydot.Edge(controller_node, endpoint_node, label="exposes"))
        
        # Add service dependencies
        for service_call in api_flow.get("service_calls", []):
            controller = service_call["class"]
            service = service_call["service"]
            if controller in controllers and service in services:
                service_node = pydot.Node(service, shape="rectangle", style="filled", fillcolor="lightyellow")
                diagram.add_node(service_node)
                diagram.add_edge(pydot.Edge(controller, service, label="uses"))
        
        # Add repository dependencies
        for repo_call in api_flow.get("repository_calls", []):
            service = repo_call["class"]
            repository = repo_call["repository"]
            if service in services and repository in repositories:
                repo_node = pydot.Node(repository, shape="rectangle", style="filled", fillcolor="lightpink")
                diagram.add_node(repo_node)
                diagram.add_edge(pydot.Edge(service, repository, label="uses"))
    
    # Save the diagram
    diagram_file = os.path.join(INDEX_DIR, "api_flow.png")
    diagram.write_png(diagram_file)
    logging.info(f"API flow diagram saved as {diagram_file}")
    
    # Display the diagram
    img = Image.open(diagram_file)
    img.show()


def scan_directory_incremental(directory):
    """Scan all Java files in the directory, skipping only test directories."""
    java_files = []
    
    logging.info(f"Starting scan of directory: {directory}")
    
    # Walk through all directories and find Java files
    for root, dirs, files in os.walk(directory):
        # Skip .git directories
        if '.git' in root:
            continue
            
        # Skip test directories
        if 'test' in root.lower():
            continue
            
        # Process Java files
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                java_files.append(file_path)
                logging.info(f"Adding file to analysis: {file_path}")

    logging.info(f"Found {len(java_files)} Java files to analyze")
    
    if not java_files:
        logging.warning("No Java files found. Skipping indexing.")
        return

    # Create index directory if it doesn't exist
    initialize_index()
    
    # Process files sequentially to avoid multiprocessing issues
    with tqdm(total=len(java_files), desc="Indexing Files") as pbar:
        for file_path in java_files:
            try:
                result = parse_java_file(file_path)
                if result and "Error" in result:
                    logging.error(result)
            except Exception as e:
                logging.error(f"Error processing {file_path}: {str(e)}")
            pbar.update(1)


def create_summary_readme():
    """Create a README.md file in the summary directory."""
    readme_content = """# Code Summarization

This directory contains summaries of the codebase generated using OpenAI's API.

## Directory Structure

- `file_summaries/`: Contains summaries of individual Java files.
- `module_summaries/`: Contains summaries of modules/packages.
- `summary_of_summaries.md`: A comprehensive overview of the entire application.

## How to Use

These summaries can be used to:

1. Quickly understand the purpose and functionality of individual files.
2. Get an overview of how different modules interact with each other.
3. Understand the high-level architecture of the application.
4. Make it easier for LLMs to answer questions about the codebase by providing context.

## Generation Process

The summaries are generated using the following process:

1. Individual file summaries are generated using the "Basic File Analysis Prompt".
2. Module summaries are generated by grouping file summaries by package/module and using the "Module Level Summarization" prompt.
3. The summary of summaries is generated using the "Creating a Summary of Summaries" prompt.

Additional analyses may include:
- Code flow analysis
- Spring context-specific analysis
"""
    
    readme_path = os.path.join(SUMMARY_DIR, "README.md")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    logging.info(f"Created README.md in {SUMMARY_DIR}")


def initialize_summary_dirs():
    """Initialize summary directories."""
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    os.makedirs(FILE_SUMMARIES_DIR, exist_ok=True)
    os.makedirs(MODULE_SUMMARIES_DIR, exist_ok=True)
    create_summary_readme()


def read_prompt_file(prompt_file):
    """Read a prompt file from the prompts directory."""
    prompt_path = os.path.join(PROMPTS_DIR, prompt_file)
    logging.info(f"Attempting to read prompt file: {prompt_path}")
    
    if not os.path.exists(prompt_path):
        logging.error(f"Prompt file does not exist: {prompt_path}")
        return None
        
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logging.info(f"Successfully read prompt file: {prompt_path} ({len(content)} characters)")
            return content
    except Exception as e:
        logging.error(f"Error reading prompt file {prompt_path}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None


def call_openai_api(prompt, max_retries=3, retry_delay=2):
    """Call OpenAI API with retry logic."""
    config = load_config()
    api_key = config.get("openai_api_key")
    
    if not api_key:
        logging.error("OpenAI API key not found in config.json. Please add 'openai_api_key' to your config.")
        return None
    
    client = openai.OpenAI(api_key=api_key)
    
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="gpt-4",  # or another model like "gpt-3.5-turbo"
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that analyzes code and provides summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error calling OpenAI API (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return None


def generate_file_summary(file_path):
    """Generate a summary for a single file."""
    try:
        logging.info(f"Starting summary generation for {file_path}")
        
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        logging.info(f"Successfully read file content for {file_path}")
        
        # Get the basic file analysis prompt
        prompt_template = read_prompt_file("Basic File Analysis Prompt.md")
        if not prompt_template:
            logging.error(f"Failed to read prompt template for {file_path}")
            return None
        
        logging.info(f"Successfully read prompt template for {file_path}")
        
        # Create the prompt with the file content
        prompt = f"{prompt_template}\n\nFile: {os.path.basename(file_path)}\n\n```java\n{file_content}\n```"
        
        logging.info(f"Calling OpenAI API for {file_path}")
        
        # Call OpenAI API
        summary = call_openai_api(prompt)
        if not summary:
            logging.error(f"OpenAI API returned no summary for {file_path}")
            return None
        
        logging.info(f"Successfully received summary from OpenAI API for {file_path}")
        
        # Save the summary
        relative_path = os.path.relpath(file_path, start=os.getcwd())
        summary_file_path = os.path.join(FILE_SUMMARIES_DIR, f"{relative_path.replace(os.sep, '_')}.md")
        
        with open(summary_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Summary of {os.path.basename(file_path)}\n\n")
            f.write(summary)
        
        logging.info(f"Generated summary for {file_path} and saved to {summary_file_path}")
        return summary_file_path
    except Exception as e:
        logging.error(f"Error generating summary for {file_path}: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return None


def generate_module_summary(module_name, file_summaries):
    """Generate a summary for a module based on file summaries."""
    try:
        # Get the module level summarization prompt
        prompt_template = read_prompt_file("Module Level Summarization.md")
        if not prompt_template:
            return None
        
        # Combine all file summaries
        combined_summaries = ""
        for summary_file in file_summaries:
            with open(summary_file, 'r', encoding='utf-8') as f:
                combined_summaries += f.read() + "\n\n---\n\n"
        
        # Create the prompt with the combined summaries
        prompt = f"{prompt_template.replace('[package/module name]', module_name)}\n\n{combined_summaries}"
        
        # Call OpenAI API
        summary = call_openai_api(prompt)
        if not summary:
            return None
        
        # Save the summary
        summary_file_path = os.path.join(MODULE_SUMMARIES_DIR, f"{module_name.replace(os.sep, '_')}.md")
        
        with open(summary_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Module Summary: {module_name}\n\n")
            f.write(summary)
        
        logging.info(f"Generated module summary for {module_name}")
        return summary_file_path
    except Exception as e:
        logging.error(f"Error generating module summary for {module_name}: {e}")
        return None


def generate_summary_of_summaries(module_summaries):
    """Generate a summary of all module summaries."""
    try:
        # Get the summary of summaries prompt
        prompt_template = read_prompt_file("Creating a Summary of Summaries.md")
        if not prompt_template:
            return None
        
        # Combine all module summaries
        combined_summaries = ""
        for summary_file in module_summaries:
            with open(summary_file, 'r', encoding='utf-8') as f:
                combined_summaries += f.read() + "\n\n---\n\n"
        
        # Create the prompt with the combined summaries
        prompt = f"{prompt_template}\n\n{combined_summaries}"
        
        # Call OpenAI API
        summary = call_openai_api(prompt)
        if not summary:
            return None
        
        # Save the summary
        with open(SUMMARY_OF_SUMMARIES_FILE, 'w', encoding='utf-8') as f:
            f.write("# Application Overview\n\n")
            f.write(summary)
        
        logging.info(f"Generated summary of summaries")
        return SUMMARY_OF_SUMMARIES_FILE
    except Exception as e:
        logging.error(f"Error generating summary of summaries: {e}")
        return None


def generate_code_flow_analysis(file_path):
    """Generate a code flow analysis for a single file."""
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Get the code flow analysis prompt
        prompt_template = read_prompt_file("Code Flow Analysis Prompt.md")
        if not prompt_template:
            return None
        
        # Create the prompt with the file content
        prompt = f"{prompt_template}\n\nFile: {os.path.basename(file_path)}\n\n```java\n{file_content}\n```"
        
        # Call OpenAI API
        analysis = call_openai_api(prompt)
        if not analysis:
            return None
        
        # Save the analysis
        relative_path = os.path.relpath(file_path, start=os.getcwd())
        analysis_file_path = os.path.join(FILE_SUMMARIES_DIR, f"{relative_path.replace(os.sep, '_')}_flow.md")
        
        with open(analysis_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Code Flow Analysis of {os.path.basename(file_path)}\n\n")
            f.write(analysis)
        
        logging.info(f"Generated code flow analysis for {file_path}")
        return analysis_file_path
    except Exception as e:
        logging.error(f"Error generating code flow analysis for {file_path}: {e}")
        return None


def generate_spring_context_analysis(file_path):
    """Generate a Spring context-specific analysis for a single file."""
    try:
        # Read the file content
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # Get the Spring context-specific prompt
        prompt_template = read_prompt_file("Spring Context-Specific Prompt.md")
        if not prompt_template:
            return None
        
        # Create the prompt with the file content
        prompt = f"{prompt_template}\n\nFile: {os.path.basename(file_path)}\n\n```java\n{file_content}\n```"
        
        # Call OpenAI API
        analysis = call_openai_api(prompt)
        if not analysis:
            return None
        
        # Save the analysis
        relative_path = os.path.relpath(file_path, start=os.getcwd())
        analysis_file_path = os.path.join(FILE_SUMMARIES_DIR, f"{relative_path.replace(os.sep, '_')}_spring.md")
        
        with open(analysis_file_path, 'w', encoding='utf-8') as f:
            f.write(f"# Spring Context Analysis of {os.path.basename(file_path)}\n\n")
            f.write(analysis)
        
        logging.info(f"Generated Spring context analysis for {file_path}")
        return analysis_file_path
    except Exception as e:
        logging.error(f"Error generating Spring context analysis for {file_path}: {e}")
        return None


def generate_summaries(directory, force_regenerate=False):
    """Generate summaries for all Java files in the directory.
    
    Args:
        directory: The directory containing Java files to summarize.
        force_regenerate: If True, regenerate summaries even if they already exist.
    """
    # Initialize summary directories
    initialize_summary_dirs()
    
    # Check if summaries already exist
    if not force_regenerate and os.path.exists(SUMMARY_OF_SUMMARIES_FILE):
        # Check if there are any file summaries
        file_summaries = [f for f in os.listdir(FILE_SUMMARIES_DIR) if f.endswith('.md')]
        if file_summaries:
            logging.info(f"Summaries already exist in {SUMMARY_DIR}. Skipping summary generation.")
            logging.info(f"Use force_regenerate=True to regenerate summaries.")
            return
    
    # Find all Java files
    java_files = []
    for root, _, files in os.walk(directory):
        # Skip .git directories
        if '.git' in root:
            continue
            
        # Skip test directories
        if 'test' in root.lower():
            continue
            
        # Process Java files
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                java_files.append(file_path)
    
    if not java_files:
        logging.warning("No Java files found. Skipping summarization.")
        return
    
    logging.info(f"Found {len(java_files)} Java files to summarize")
    
    # Generate file summaries
    file_summaries = []
    with tqdm(total=len(java_files), desc="Generating File Summaries") as pbar:
        for file_path in java_files:
            # Skip if summary already exists and not forcing regeneration
            relative_path = os.path.relpath(file_path, start=os.getcwd())
            summary_file_path = os.path.join(FILE_SUMMARIES_DIR, f"{relative_path.replace(os.sep, '_')}.md")
            if not force_regenerate and os.path.exists(summary_file_path):
                file_summaries.append(summary_file_path)
                logging.info(f"Summary already exists for {file_path}. Skipping.")
                pbar.update(1)
                continue
                
            summary_file = generate_file_summary(file_path)
            if summary_file:
                file_summaries.append(summary_file)
            pbar.update(1)
    
    # Group files by package/module
    module_files = defaultdict(list)
    for summary_file in file_summaries:
        # Extract the original file path from the summary file name
        original_path = os.path.basename(summary_file).replace('.md', '')
        original_path = original_path.replace('_', os.sep)
        
        # Get the package/module name
        package_parts = original_path.split(os.sep)
        if len(package_parts) >= 4 and 'java' in package_parts:
            java_index = package_parts.index('java')
            if java_index + 1 < len(package_parts):
                # Use the first package after 'java' as the module name
                module_name = package_parts[java_index + 1]
                module_files[module_name].append(summary_file)
    
    # Generate module summaries
    module_summaries = []
    with tqdm(total=len(module_files), desc="Generating Module Summaries") as pbar:
        for module_name, summary_files in module_files.items():
            # Skip if module summary already exists and not forcing regeneration
            module_summary_path = os.path.join(MODULE_SUMMARIES_DIR, f"{module_name.replace(os.sep, '_')}.md")
            if not force_regenerate and os.path.exists(module_summary_path):
                module_summaries.append(module_summary_path)
                logging.info(f"Module summary already exists for {module_name}. Skipping.")
                pbar.update(1)
                continue
                
            module_summary = generate_module_summary(module_name, summary_files)
            if module_summary:
                module_summaries.append(module_summary)
            pbar.update(1)
    
    # Generate summary of summaries
    if module_summaries:
        # Skip if summary of summaries already exists and not forcing regeneration
        if not force_regenerate and os.path.exists(SUMMARY_OF_SUMMARIES_FILE):
            logging.info(f"Summary of summaries already exists. Skipping.")
        else:
            summary_of_summaries = generate_summary_of_summaries(module_summaries)
            if summary_of_summaries:
                logging.info(f"Summary of summaries generated: {summary_of_summaries}")
    else:
        logging.warning("No module summaries generated. Skipping summary of summaries.")


def generate_api_flow_for_llm(directory):
    """Generate API flow representation in JSON format for better LLM consumption.
    
    This creates a more structured representation of the API endpoints and their relationships
    to controllers, services, and repositories for easier consumption by LLMs.
    """
    logging.info("Generating API flow representation for LLM consumption...")
    
    # Load the existing API flow data
    api_flow_data = load_from_file(API_FLOW_JSON)
    if not api_flow_data:
        logging.warning("No API flow data found. Run scan_directory_incremental first.")
        return None
    
    # Load the index data to get more information about the components
    index_data = load_from_file(INDEX_JSON)
    if not index_data:
        logging.warning("No index data found. Run scan_directory_incremental first.")
        return None
    
    # Create the enhanced API flow representation
    enhanced_api_flow = {}
    
    for endpoint_path, endpoint_data in api_flow_data.items():
        for endpoint in endpoint_data.get("endpoints", []):
            endpoint_key = f"{endpoint_path}:{endpoint.get('http_method', 'GET')}"
            
            # Initialize the endpoint entry
            if endpoint_key not in enhanced_api_flow:
                enhanced_api_flow[endpoint_key] = {
                    "endpoint": endpoint_path,
                    "method": endpoint.get("http_method", "GET"),
                    "controller": {
                        "file": f"{endpoint.get('class', '')}.java",
                        "method": endpoint.get("method", ""),
                        "responsibility": f"Handles {endpoint_path} requests"
                    },
                    "serviceChain": [],
                    "repositoryAccess": [],
                    "dataModels": [],
                    "dependencies": []
                }
            
            # Add service chain information
            for service_call in endpoint_data.get("service_calls", []):
                service_info = {
                    "file": f"{service_call.get('service', '')}.java",
                    "method": "Unknown",  # We don't have this information in the current data
                    "responsibility": f"Business logic for {endpoint_path}"
                }
                
                if service_info not in enhanced_api_flow[endpoint_key]["serviceChain"]:
                    enhanced_api_flow[endpoint_key]["serviceChain"].append(service_info)
                
                # Add as a dependency as well
                if service_info["file"] not in enhanced_api_flow[endpoint_key]["dependencies"]:
                    enhanced_api_flow[endpoint_key]["dependencies"].append(service_info["file"])
            
            # Try to find repository access information from the index data
            for file_path, file_data in index_data.items():
                # Check if this is a repository file
                if "Repository" in file_path:
                    # Add to repository access
                    repo_info = {
                        "file": os.path.basename(file_path),
                        "method": "Unknown",  # We don't have this information in the current data
                        "dataAccessed": os.path.basename(file_path).replace("Repository.java", "")
                    }
                    
                    if repo_info not in enhanced_api_flow[endpoint_key]["repositoryAccess"]:
                        enhanced_api_flow[endpoint_key]["repositoryAccess"].append(repo_info)
                
                # Check if this is a model file
                elif "models" in file_path or "entities" in file_path:
                    model_file = os.path.basename(file_path)
                    if model_file not in enhanced_api_flow[endpoint_key]["dataModels"]:
                        enhanced_api_flow[endpoint_key]["dataModels"].append(model_file)
    
    # Save the enhanced API flow representation
    enhanced_api_flow_file = os.path.join(SUMMARY_DIR, "enhanced_api_flow.json")
    with open(enhanced_api_flow_file, 'w', encoding='utf-8') as f:
        json.dump(enhanced_api_flow, f, indent=2)
    
    logging.info(f"Enhanced API flow representation saved to {enhanced_api_flow_file}")
    return enhanced_api_flow_file


def generate_component_relationship_matrix():
    """Generate a component relationship matrix showing dependencies between components.
    
    This creates a markdown table showing which components depend on which other components,
    and which components use each component.
    """
    logging.info("Generating component relationship matrix...")
    
    # Load the index data
    index_data = load_from_file(INDEX_JSON)
    if not index_data:
        logging.warning("No index data found. Run scan_directory_incremental first.")
        return None
    
    # Create dictionaries to track dependencies
    depends_on = defaultdict(set)
    used_by = defaultdict(set)
    
    # Process all files to build the dependency graph
    for file_path, file_data in index_data.items():
        component_name = os.path.basename(file_path).replace(".java", "")
        
        # Process dependencies
        for dependency in file_data.get("dependencies", []):
            # Skip external dependencies
            if any(ext_pkg in dependency for ext_pkg in EXTERNAL_PACKAGES):
                continue
                
            # Extract the component name from the dependency
            dep_parts = dependency.split(".")
            if len(dep_parts) > 0:
                dep_component = dep_parts[-1]
                depends_on[component_name].add(dep_component)
                used_by[dep_component].add(component_name)
    
    # Create the markdown table
    matrix_content = "# Component Relationship Matrix\n\n"
    matrix_content += "| Component | Depends On | Used By |\n"
    matrix_content += "|-----------|-----------|--------|\n"
    
    # Sort components alphabetically
    components = sorted(set(list(depends_on.keys()) + list(used_by.keys())))
    
    for component in components:
        deps = ", ".join(sorted(depends_on[component])) if component in depends_on else ""
        users = ", ".join(sorted(used_by[component])) if component in used_by else ""
        matrix_content += f"| {component} | {deps} | {users} |\n"
    
    # Save the matrix
    matrix_file = os.path.join(SUMMARY_DIR, "component_relationship_matrix.md")
    with open(matrix_file, 'w', encoding='utf-8') as f:
        f.write(matrix_content)
    
    logging.info(f"Component relationship matrix saved to {matrix_file}")
    return matrix_file


def generate_llm_prompt_templates():
    """Generate effective prompt templates for LLM analysis.
    
    This creates a set of prompt templates that can be used to analyze the codebase
    with LLMs, including templates for feature implementation, code change impact,
    and self-correction mechanisms.
    """
    logging.info("Generating LLM prompt templates...")
    
    # Create the prompts directory if it doesn't exist
    llm_prompts_dir = os.path.join(SUMMARY_DIR, "llm_prompts")
    os.makedirs(llm_prompts_dir, exist_ok=True)
    
    # General analysis prompt template
    general_analysis_template = """# Spring Boot Application Analysis

## Application Context
{insert relevant high-level application summary}

## Components Relevant to Query
{insert summaries of the 3-5 most relevant components}

## API Flows Related to Query
{insert API flow data for endpoints relevant to the query}

## Question
{insert specific question}

## Instructions
1. Analyze the question in relation to the provided Spring Boot application context
2. Provide a detailed technical response addressing the question
3. Cite specific code files and components in your answer using the format [FileName.java]
4. Identify any potential impacts or considerations across components
5. If any information seems missing, note assumptions you're making
"""
    
    # Feature implementation prompt template
    feature_implementation_template = """# Feature Implementation Analysis

## Application Context
{insert relevant high-level application summary}

## Components Relevant to Feature
{insert summaries of the 3-5 most relevant components}

## API Flows Related to Feature
{insert API flow data for endpoints relevant to the feature}

## Feature Request
{insert feature description}

## Instructions
1. Analyze how the requested feature would be implemented in this Spring Boot application
2. Identify which existing components would need to be modified
3. Specify any new components that would need to be created
4. Describe the changes required to each component
5. Identify potential challenges or considerations for implementation
6. Cite specific code files and components in your answer using the format [FileName.java]

## Example Response Format:
```
Implementing [Feature Name] would require:

1. Modifications to existing components:
   - [ExistingComponent1.java]: {specific changes}
   - [ExistingComponent2.java]: {specific changes}

2. New components needed:
   - [NewComponent1.java]: {purpose and functionality}
   - [NewComponent2.java]: {purpose and functionality}

3. Implementation steps:
   {step-by-step implementation plan}

4. Potential challenges:
   {list of challenges and considerations}
```
"""
    
    # Code change impact prompt template
    code_change_impact_template = """# Code Change Impact Analysis

## Application Context
{insert relevant high-level application summary}

## Component Relationship Matrix
{insert relevant portion of component relationship matrix}

## Proposed Change
{insert description of proposed code change}

## Instructions
1. Analyze the impact of the proposed change on the Spring Boot application
2. Identify all components that would be directly affected by the change
3. Identify all components that would be indirectly affected through dependencies
4. Assess the scope of the change (isolated vs. widespread)
5. Identify potential risks or considerations
6. Cite specific code files and components in your answer using the format [FileName.java]

## Example Response Format:
```
Changing [Component] would impact:

1. Direct impacts:
   - [Component1.java]: {specific impact}
   - [Component2.java]: {specific impact}

2. Indirect impacts (through dependencies):
   - [Component3.java] depends on [Component1.java]: {specific impact}
   - [Component4.java] uses [Component2.java]: {specific impact}

3. Scope assessment:
   {assessment of whether the change is isolated or widespread}

4. Risks and considerations:
   {list of risks and considerations}
```
"""
    
    # Self-correction mechanism prompt template
    self_correction_template = """# Self-Correction Review

## Original Response
{insert original LLM response}

## Application Context
{insert relevant high-level application summary}

## Component Relationship Matrix
{insert relevant portion of component relationship matrix}

## Instructions
Review the original response and verify:
1. Are all cited files actually mentioned in the application context?
2. Are the described relationships between components consistent with the provided component relationship matrix?
3. Are the described API flows consistent with the provided API flow data?
4. Does the impact analysis consider all dependent components from the relationship matrix?
5. Correct any inconsistencies and explain the corrections.

## Example Response Format:
```
Review of original response:

1. File reference accuracy:
   - [CorrectReference.java]: Verified in application context
   - [IncorrectReference.java]: Not found in application context, should be [CorrectFile.java]

2. Component relationship accuracy:
   - [Component1.java] correctly identified as depending on [Component2.java]
   - [Component3.java] incorrectly described as using [Component4.java], no such relationship exists

3. API flow accuracy:
   - The described flow for [/api/endpoint] is consistent with the API flow data
   - The described flow for [/api/another] is inconsistent, should include [MissingComponent.java]

4. Impact analysis completeness:
   - [MissingDependentComponent.java] was not considered but would be affected

Corrected response:
{insert corrected response}
```
"""
    
    # Save the templates
    with open(os.path.join(llm_prompts_dir, "general_analysis_template.md"), 'w', encoding='utf-8') as f:
        f.write(general_analysis_template)
    
    with open(os.path.join(llm_prompts_dir, "feature_implementation_template.md"), 'w', encoding='utf-8') as f:
        f.write(feature_implementation_template)
    
    with open(os.path.join(llm_prompts_dir, "code_change_impact_template.md"), 'w', encoding='utf-8') as f:
        f.write(code_change_impact_template)
    
    with open(os.path.join(llm_prompts_dir, "self_correction_template.md"), 'w', encoding='utf-8') as f:
        f.write(self_correction_template)
    
    logging.info(f"LLM prompt templates saved to {llm_prompts_dir}")
    return llm_prompts_dir


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate code summaries and diagrams")
    parser.add_argument("--force-clone", action="store_true", help="Force clone repository even if it already exists")
    parser.add_argument("--force-summaries", action="store_true", help="Force regenerate summaries even if they already exist")
    parser.add_argument("--skip-diagrams", action="store_true", help="Skip generating diagrams")
    parser.add_argument("--skip-summaries", action="store_true", help="Skip generating summaries")
    parser.add_argument("--llm-optimizations", action="store_true", help="Generate LLM-optimized summaries and templates")
    args = parser.parse_args()
    
    # Load configuration
    config = load_config()
    repo_url = config.get("repo_url", "https://github.com/pauldragoslav/Spring-boot-Banking")
    clone_dir = config.get("clone_dir", "./gleanclone")

    # Clone repository if needed or forced
    if args.force_clone and os.path.exists(clone_dir):
        import shutil
        logging.info(f"Forcing clone: removing existing directory {clone_dir}")
        shutil.rmtree(clone_dir)
    
    clone_repo(repo_url, clone_dir)
    
    # Initialize index and scan directory
    initialize_index()
    scan_directory_incremental(clone_dir)

    # Generate diagrams if not skipped
    if not args.skip_diagrams:
        logging.info("Generating diagrams...")
        generate_sequence_diagram()
        generate_c4_diagrams()
        generate_api_flow_diagram()
    else:
        logging.info("Skipping diagram generation.")

    # Generate summaries if not skipped
    if not args.skip_summaries:
        logging.info("Generating summaries...")
        generate_summaries(clone_dir, force_regenerate=args.force_summaries)
    else:
        logging.info("Skipping summary generation.")
        
    # Generate LLM optimizations if requested
    if args.llm_optimizations:
        logging.info("Generating LLM optimizations...")
        
        # Generate enhanced API flow representation
        api_flow_file = generate_api_flow_for_llm(clone_dir)
        if api_flow_file:
            logging.info(f"Enhanced API flow representation generated: {api_flow_file}")
        
        # Generate component relationship matrix
        matrix_file = generate_component_relationship_matrix()
        if matrix_file:
            logging.info(f"Component relationship matrix generated: {matrix_file}")
        
        # Generate LLM prompt templates
        templates_dir = generate_llm_prompt_templates()
        if templates_dir:
            logging.info(f"LLM prompt templates generated in: {templates_dir}")
            
        logging.info("LLM optimizations completed.")
    else:
        logging.info("Skipping LLM optimizations. Use --llm-optimizations to generate them.")