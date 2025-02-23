This script indexes Java code, tracks dependencies, and supports incremental indexing for a given Git repository. It also performs impact analysis, dependency graph generation, and query-based lookups.

Key Features & Functionality

**Repository Management**
Clones or updates a Git repository (clone_repo function).
Uses gitpython to fetch the latest changes.

**Indexing Java Code**
Parses Java files using javalang.parse.parse().
Extracts:
  Classes (names and locations).
  Methods (names, return types, parameters, locations).
  Fields (class attributes and their types).
  Dependencies (imported modules/packages).
  Call Graph (tracks method calls between files).
  Inheritance (tracks parent-child relationships in class hierarchies).
  Annotations (tracks metadata in Java files).

**Incremental Indexing & Storage Optimization**
Uses SHA-256 checksums to detect modified Java files (avoids re-indexing unchanged files).
Stores indexed data using shelve (a binary key-value store) for fast lookups.

**Query Capabilities**
Finds all references to a given method (query_references function).
Tracks method calls between Java files.
Supports future extension for more complex queries.

**Performance & Logging**
Uses ProcessPoolExecutor for parallel parsing of Java files.
Tracks indexing progress using tqdm progress bar.
Uses structured logging (logging.basicConfig) for debugging.

**Impact Analysis & Dependency Tracking**
Builds a call graph to analyze method dependencies.
Tracks references to determine how code changes might impact other parts of the project.

Generates a dependency graph using networkx.

**How It Works**
Loads configuration (e.g., repo URL) from config.json.
Clones/Pulls the repository (clone_repo).
Initializes storage (initialize_index).
Scans Java files incrementally (scan_directory_incremental).
Parses Java files & updates the index (parse_java_file).
Supports querying (query_references).

**Strengths**
Optimized incremental indexing (SHA-256 checksum for change detection).
Uses shelve instead of JSON (faster data retrieval).
Supports parallel processing (efficient multi-threading).
Tracks method references, class inheritance, and dependencies.
Generates dependency graphs for visualization.

