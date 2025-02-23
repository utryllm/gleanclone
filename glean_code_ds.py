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

# Setup structured logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

INDEX_DIR = "code_index"
MOD_TIMES_FILE = "file_mod_times.json"
CONFIG_FILE = "config.json"
GRAPH_FILE = "dependency_graph.dot"
INDEX_JSON = os.path.join(INDEX_DIR, "index.json")  # JSON file instead of shelve

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

CONFIG = load_config()

def clone_repo(repo_url, clone_dir):
    try:
        if not os.path.exists(clone_dir):
            git.Repo.clone_from(repo_url, clone_dir)
        else:
            repo = git.Repo(clone_dir)
            repo.remotes.origin.pull()
    except git.exc.GitError as e:
        logging.error(f"Error cloning repository: {e}")
        return

def initialize_index():
    os.makedirs(INDEX_DIR, exist_ok=True)
    if not os.path.exists(INDEX_JSON) or os.stat(INDEX_JSON).st_size == 0:
        logging.warning(f"{INDEX_JSON} was missing or empty. Initializing with an empty dictionary.")
        save_to_file(INDEX_JSON, {})  # ✅ Ensures JSON file always has valid data

def save_to_file(file_name, data):
    file_path = file_name if os.path.isabs(file_name) else os.path.join(INDEX_DIR, file_name)
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Ensure directory exists
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logging.error(f"Error saving to file {file_path}: {e}")


def load_from_file(file_name):
    file_path = file_name if os.path.isabs(file_name) else os.path.join(INDEX_DIR, file_name)
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error loading file {file_path}: {e}")
    return {}

def build_dependency_graph():
    index_data = load_from_file(INDEX_JSON)
    G = nx.DiGraph()

    for file_path, data in index_data.items():
        class_names = [cls["name"] for cls in data.get("classes", [])]
        for dependency in data.get("dependencies", []):
            for class_name in class_names:
                G.add_edge(class_name, dependency)

    nx.drawing.nx_pydot.write_dot(G, os.path.join(INDEX_DIR, GRAPH_FILE))
    logging.info(f"Dependency graph saved to {GRAPH_FILE}")

    # Optional: Save as an image
    import matplotlib.pyplot as plt
    plt.figure(figsize=(10, 6))
    nx.draw(G, with_labels=True, node_color='lightblue', edge_color='gray', font_size=10)
    plt.savefig(os.path.join(INDEX_DIR, "dependency_graph.png"))
    logging.info("Dependency graph visualization saved as dependency_graph.png")


def compute_checksum(file_path):
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except IOError as e:
        logging.error(f"Error computing checksum for {file_path}: {e}")
        return None

def parse_java_file(file_path):
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
            if node.extends:
                parsed_data["inheritance"].append({"class": node.name, "extends": node.extends.name})
            defined_symbols[node.name] = file_path
        elif isinstance(node, javalang.tree.MethodDeclaration):
            parsed_data["methods"].append({
                "name": node.name,
                "line_number": node.position.line,
                "return_type": node.return_type.name if node.return_type else "void",
                "parameters": [param.type.name for param in node.parameters]
            })
            defined_symbols[node.name] = file_path
        elif isinstance(node, javalang.tree.FieldDeclaration):
            parsed_data["fields"].append({
                "name": node.declarators[0].name,
                "type": node.type.name,
                "line_number": node.position.line
            })
        elif isinstance(node, javalang.tree.Import):
            parsed_data["dependencies"].append(node.path)
        elif isinstance(node, javalang.tree.Annotation):
            for subpath in path:
                if isinstance(subpath, javalang.tree.Annotation):
                    parsed_data["annotations"].append({"name": node.name, "element": subpath.name})

    for path, node in tree:
        if isinstance(node, javalang.tree.MethodInvocation):
            if node.member in defined_symbols:
                parsed_data["call_graph"].append({"caller": file_path, "callee": defined_symbols[node.member]})
                parsed_data["references"].append({"file": file_path, "method": node.member})

    index_data[file_path] = parsed_data
    save_to_file(INDEX_JSON, index_data)

    mod_times = load_from_file(MOD_TIMES_FILE)
    mod_times[file_path] = compute_checksum(file_path)
    save_to_file(MOD_TIMES_FILE, mod_times)

def query_references(method_name):
    index_data = load_from_file(INDEX_JSON)
    results = []
    for file_path, data in index_data.items():
        for ref in data.get("references", []):
            if ref["method"] == method_name:
                results.append(ref)
    return results

def scan_directory_incremental(directory):
    java_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                java_files.append(file_path)  # ✅ Always add Java files for processing

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
    repo_url = config.get("repo_url", "https://github.com/pauldragoslav/Spring-boot-Banking.git")
    clone_dir = config.get("clone_dir", "./cloned_repo")

    clone_repo(repo_url, clone_dir)
    initialize_index()
    scan_directory_incremental(clone_dir)
    # Generate and save dependency graph
    build_dependency_graph()
