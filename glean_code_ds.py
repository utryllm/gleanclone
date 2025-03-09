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

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

INDEX_DIR = "code_index"
MOD_TIMES_FILE = "file_mod_times.json"
CONFIG_FILE = "config.json"
GRAPH_FILE = "dependency_graph.dot"
INDEX_JSON = os.path.join(INDEX_DIR, "index.json")
API_FLOW_JSON = os.path.join(INDEX_DIR, "api_flow.json")
SEQUENCE_DIAGRAM_FILE = os.path.join(INDEX_DIR, "sequence_diagram.puml")

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
            logging.warning(f"Directory {clone_dir} already exists. Deleting and re-cloning...")
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


if __name__ == "__main__":
    config = load_config()
    repo_url = config.get("repo_url", "https://github.com/pauldragoslav/Spring-boot-Banking")
    clone_dir = config.get("clone_dir", "./gleanclone")

    clone_repo(repo_url, clone_dir)
    initialize_index()
    scan_directory_incremental(clone_dir)

    # Generate sequence diagram
    generate_sequence_diagram()
    generate_c4_diagrams()
    generate_api_flow_diagram()