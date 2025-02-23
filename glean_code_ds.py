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

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

INDEX_DIR = "code_index"
MOD_TIMES_FILE = "file_mod_times.json"
CONFIG_FILE = "config.json"
GRAPH_FILE = "dependency_graph.dot"
INDEX_JSON = os.path.join(INDEX_DIR, "index.json")
SEQUENCE_DIAGRAM_FILE = os.path.join(INDEX_DIR, "sequence_diagram.puml")

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
                os.chmod(os.path.join(root, file_name), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH)

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
    
    parsed_data = {
        "classes": [], "methods": [], "fields": [], "dependencies": [],
        "call_graph": [], "inheritance": [], "annotations": [], "references": []
    }
    defined_symbols = {}

    for path, node in tree:
        if isinstance(node, javalang.tree.ClassDeclaration):
            parsed_data["classes"].append({"name": node.name, "line_number": node.position.line})
            defined_symbols[node.name] = file_path
        elif isinstance(node, javalang.tree.MethodDeclaration):
            parsed_data["methods"].append({"name": node.name, "line_number": node.position.line})
            defined_symbols[node.name] = file_path
        elif isinstance(node, javalang.tree.Import):
            parsed_data["dependencies"].append(node.path)

    # Extract method calls
    for path, node in tree:
        if isinstance(node, javalang.tree.MethodInvocation):
            parsed_data["call_graph"].append({
                "caller": file_path,
                "callee": node.member
            })

    index_data[file_path] = parsed_data
    save_to_file(INDEX_JSON, index_data)

    logging.info(f"Extracted data from {file_path}: {parsed_data}")  # ✅ Log parsed data

    return f"Successfully parsed {file_path}"

import matplotlib.pyplot as plt
import pydot
from PIL import Image

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

def generate_c4_diagram():
    """Generates a C4 component diagram (C3 level) from extracted Java class relationships."""
    index_data = load_from_file(INDEX_JSON)

    if not index_data:
        logging.warning("No data found in index.json. Skipping C4 diagram generation.")
        return

    diagram_file = os.path.join(INDEX_DIR, "c4_diagram.png")
    graph = pydot.Dot(graph_type="digraph", bgcolor="white", label="C4 Component Diagram", fontsize="20", labelloc="t")

    class_nodes = {}

    # ✅ Extract classes and their dependencies
    for file_path, data in index_data.items():
        class_name = os.path.basename(file_path).replace(".java", "")

        # ✅ Create nodes for classes
        if class_name not in class_nodes:
            class_nodes[class_name] = pydot.Node(class_name, shape="rectangle", style="filled", fillcolor="lightblue")
            graph.add_node(class_nodes[class_name])

        # ✅ Create edges for dependencies
        for dependency in data.get("dependencies", []):
            dep_name = dependency.split(".")[-1]  # Extract simple class name from import path
            if dep_name not in class_nodes:
                class_nodes[dep_name] = pydot.Node(dep_name, shape="rectangle", style="filled", fillcolor="lightgreen")
                graph.add_node(class_nodes[dep_name])

            graph.add_edge(pydot.Edge(class_nodes[class_name], class_nodes[dep_name], label="depends on"))

    # ✅ Save as PNG
    graph.write_png(diagram_file)
    logging.info(f"C4 Component Diagram saved as {diagram_file}")

    # ✅ Display the PNG (Optional)
    img = Image.open(diagram_file)
    img.show()

def scan_directory_incremental(directory):
    java_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                java_files.append(file_path)

    if not java_files:
        logging.warning("No Java files found. Skipping indexing.")
        return

    with tqdm(total=len(java_files), desc="Indexing Files") as pbar:
        with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            for result in executor.map(parse_java_file, java_files):
                pbar.update(1)
                if result and "Error" in result:
                    print(result)

if __name__ == "__main__":
    config = load_config()
    repo_url = config.get("repo_url", "https://github.com/cbarkinozer/OnlineBankingRestAPI.git")
    clone_dir = config.get("clone_dir", "./cloned_repo")

    clone_repo(repo_url, clone_dir)
    initialize_index()
    scan_directory_incremental(clone_dir)

    # Generate sequence diagram
    generate_sequence_diagram()
    generate_c4_diagram()
