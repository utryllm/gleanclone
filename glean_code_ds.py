import os
import json
import javalang
import git
import hashlib
import logging
import logging.config
import concurrent.futures
from tqdm import tqdm
from collections import defaultdict
import shelve
import networkx as nx
import urllib.parse
import unittest
from contextlib import contextmanager

# Setup structured logging
logging.config.dictConfig({
    "version": 1,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(levelname)s %(message)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "glean_code.log",
            "formatter": "json",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console", "file"],
    },
})

# Configuration
INDEX_DIR = "code_index"
MOD_TIMES_FILE = "file_mod_times.json"
CONFIG_FILE = "config.json"
GRAPH_FILE = "dependency_graph.dot"

def load_config():
    """
    Load configuration from config.json.
    Returns:
        dict: Configuration settings.
    """
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def validate_config(config):
    """
    Validate the configuration settings.
    Args:
        config (dict): Configuration settings.
    Returns:
        dict: Validated configuration.
    Raises:
        ValueError: If configuration is invalid.
    """
    if "repo_url" not in config:
        raise ValueError("Missing 'repo_url' in config")
    if not urllib.parse.urlparse(config["repo_url"]).scheme:
        raise ValueError("Invalid 'repo_url' in config")
    return config

CONFIG = validate_config(load_config())

@contextmanager
def open_index_db():
    """
    Context manager for opening the shelve database.
    Yields:
        shelve.DbfilenameShelf: The opened shelve database.
    """
    db = shelve.open(os.path.join(INDEX_DIR, "index.db"))
    try:
        yield db
    finally:
        db.close()

def clone_repo(repo_url, clone_dir):
    """
    Clone a Git repository from the given URL into the specified directory.
    If the directory already exists, pull the latest changes.
    Args:
        repo_url (str): The URL of the Git repository.
        clone_dir (str): The directory to clone the repository into.
    """
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
    """
    Initialize the index directory and required files.
    """
    os.makedirs(INDEX_DIR, exist_ok=True)
    if not os.path.exists(os.path.join(INDEX_DIR, MOD_TIMES_FILE)):
        save_to_file(MOD_TIMES_FILE, {})

def save_to_file(file_name, data):
    """
    Save data to a file in the index directory.
    Args:
        file_name (str): The name of the file.
        data (dict or list): The data to save.
    """
    file_path = os.path.join(INDEX_DIR, file_name)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        logging.error(f"Error saving to file {file_path}: {e}")

def load_from_file(file_name):
    """
    Load data from a file in the index directory.
    Args:
        file_name (str): The name of the file.
    Returns:
        dict or list: The loaded data.
    """
    file_path = os.path.join(INDEX_DIR, file_name)
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error(f"Error loading file {file_path}: {e}")
    return {} if file_name == MOD_TIMES_FILE else []

def compute_checksum(file_path):
    """
    Compute the SHA-256 checksum of a file.
    Args:
        file_path (str): The path to the file.
    Returns:
        str: The checksum of the file.
    """
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except IOError as e:
        logging.error(f"Error computing checksum for {file_path}: {e}")
        return None

def parse_java_file(file_path):
    """
    Parse a Java file and update the index.
    Args:
        file_path (str): The path to the Java file.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = javalang.parse.parse(f.read())
    except (javalang.parser.JavaSyntaxError, FileNotFoundError, IOError) as e:
        logging.error(f"Error parsing Java file {file_path}: {e}")
        return

    with open_index_db() as index_db:
        # Remove existing entries for this file
        index_db.pop(file_path, None)

        parsed_data = {
            "classes": [], "methods": [], "fields": [], "dependencies": [], "call_graph": [],
            "interfaces": [], "enums": [], "annotations": []
        }
        defined_symbols = {}

        for path, node in tree:
            if isinstance(node, javalang.tree.ClassDeclaration):
                parsed_data["classes"].append({"name": node.name, "line_number": node.position.line})
                defined_symbols[node.name] = file_path
            elif isinstance(node, javalang.tree.MethodDeclaration):
                parsed_data["methods"].append({
                    "name": node.name,
                    "line_number": node.position.line,
                    "return_type": node.return_type.name if node.return_type else "void",
                    "parameters": [{"type": param.type.name, "name": param.name} for param in node.parameters],
                })
                defined_symbols[node.name] = file_path
            elif isinstance(node, javalang.tree.FieldDeclaration):
                parsed_data["fields"].append({
                    "name": node.declarators[0].name,
                    "type": node.type.name,
                    "line_number": node.position.line,
                })
            elif isinstance(node, javalang.tree.Import):
                parsed_data["dependencies"].append(node.path)
            elif isinstance(node, javalang.tree.InterfaceDeclaration):
                parsed_data["interfaces"].append({"name": node.name, "line_number": node.position.line})
            elif isinstance(node, javalang.tree.EnumDeclaration):
                parsed_data["enums"].append({"name": node.name, "line_number": node.position.line})
            elif isinstance(node, javalang.tree.AnnotationDeclaration):
                parsed_data["annotations"].append({"name": node.name, "line_number": node.position.line})

        for path, node in tree:
            if isinstance(node, javalang.tree.MethodInvocation):
                if node.member in defined_symbols:
                    parsed_data["call_graph"].append({"caller": file_path, "callee": defined_symbols[node.member]})

        index_db[file_path] = parsed_data

    mod_times = load_from_file(MOD_TIMES_FILE)
    mod_times[file_path] = compute_checksum(file_path)
    save_to_file(MOD_TIMES_FILE, mod_times)

def scan_directory_incremental(directory):
    """
    Scan a directory for Java files and index them incrementally.
    Args:
        directory (str): The directory to scan.
    """
    mod_times = load_from_file(MOD_TIMES_FILE)
    java_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                file_path = os.path.join(root, file)
                checksum = compute_checksum(file_path)
                if file_path not in mod_times or mod_times[file_path] != checksum:
                    java_files.append(file_path)

    with tqdm(total=len(java_files), desc="Indexing Files") as pbar:
        with concurrent.futures.ProcessPoolExecutor(max_workers=os.cpu_count()) as executor:
            for _ in executor.map(parse_java_file, java_files):
                pbar.update(1)

def generate_dependency_graph():
    """
    Generate a dependency graph from the indexed data.
    """
    with open_index_db() as index_db:
        G = nx.DiGraph()
        for file_path, data in index_db.items():
            for dep in data.get("dependencies", []):
                G.add_edge(file_path, dep)
        nx.drawing.nx_pydot.write_dot(G, os.path.join(INDEX_DIR, GRAPH_FILE))
        logging.info(f"Dependency graph saved as {GRAPH_FILE}")

def query_methods_by_class(class_name):
    """
    Query methods by class name.
    Args:
        class_name (str): The name of the class.
    Returns:
        list: A list of methods in the class.
    """
    with open_index_db() as index_db:
        results = []
        for file_path, data in index_db.items():
            for method in data.get("methods", []):
                if method["name"] == class_name:
                    results.append({"file": file_path, "method": method})
        return results

def query_classes_by_dependency(dependency):
    """
    Query classes that use a specific dependency.
    Args:
        dependency (str): The dependency to search for.
    Returns:
        list: A list of classes that use the dependency.
    """
    with open_index_db() as index_db:
        results = []
        for file_path, data in index_db.items():
            if dependency in data.get("dependencies", []):
                results.append(file_path)
        return results

def query_call_graph(method_name):
    """
    Query the call graph for a specific method.
    Args:
        method_name (str): The name of the method.
    Returns:
        list: A list of call graph entries for the method.
    """
    with open_index_db() as index_db:
        results = []
        for file_path, data in index_db.items():
            for call in data.get("call_graph", []):
                if call["callee"] == method_name:
                    results.append(call)
        return results

class TestGleanCode(unittest.TestCase):
    """
    Unit tests for the glean_code module.
    """
    def test_parse_java_file(self):
        # Create a sample Java file and test parsing
        pass

    def test_query_methods_by_class(self):
        # Test querying methods in a class
        pass

if __name__ == "__main__":
    config = load_config()
    repo_url = config.get("repo_url", "https://github.com/your-repo.git")
    clone_dir = config.get("clone_dir", "./cloned_repo")

    clone_repo(repo_url, clone_dir)
    initialize_index()
    scan_directory_incremental(clone_dir)
    generate_dependency_graph()