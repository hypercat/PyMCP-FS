# Python (MCP) Filesystem Server

This repository contains a robust Python-based **Model Context Protocol (MCP) Filesystem Server**. It enables AI models and applications to securely interact with the host system's file directories through a defined set of tools, allowing for operations like reading, writing, moving, and listing files and directories.

The server is built upon the `fastmcp` library and adheres to the [Model Context Protocol](https://github.com/modelcontextprotocol), providing a standardized way for AI tools to manage and access files within specified boundaries.

It's inspired by this [example typescript implementation](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem).

-----

## Features

  * **Secure Directory Access:** All file operations are strictly confined to a predefined list of allowed directories, preventing unauthorized access to other parts of the filesystem.
  * **Comprehensive File Operations:**
      * **`read_file`**: Read the complete contents of a single text file.
      * **`read_multiple_files`**: Efficiently read content from multiple files, returning results with clear path references.
      * **`write_file`**: Create new files or overwrite existing ones with specified content.
      * **`edit_file`**: Apply line-based edits to text files, with an option for a dry run to preview changes as a Git-style diff.
      * **`create_directory`**: Create new directories, including nested structures, or ensure their existence.
      * **`list_directory`**: Get a detailed listing of files and subdirectories within a given path.
      * **`directory_tree`**: Generate a recursive JSON tree structure of files and directories for a clear hierarchical view.
      * **`move_file`**: Move or rename files and directories.
      * **`search_files`**: Recursively search for files and directories matching a pattern, with optional exclusion patterns.
      * **`get_file_info`**: Retrieve detailed metadata (size, timestamps, permissions) about files or directories.
  * **Dynamic Allowed Directories:** Configurable via command-line arguments to specify exactly which directories the server can access.
  * **Robust Logging:** Integrates comprehensive logging with support for different log levels and output to both `stderr` (for MCP compliance) and an optional rotating log file.
  * **Error Handling:** Provides detailed error messages for common issues like access denied, file not found, or permission errors.
  * **Line Ending Normalization:** Handles `\r\n` and `\n` line endings consistently for `edit_file` operations.
  * **Symlink Protection:** Validates the real path of symlinks to prevent escaping allowed directories.

-----

## Getting Started

### Prerequisites

  * **Python 3.8+**: The server is developed and tested with modern Python versions.
  * **`fastmcp` library**: This server uses the `fastmcp` library for MCP protocol handling. You'll need to install it.

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/hypercat/PyMCP-FS.git
    cd PyMCP-FS
    ```

2.  **Initialize project with `uv`:**

    ```bash
    uv pip install -r pyproject.toml
    ```

-----

## Usage

### Running the MCP Server (`main.py`)

The MCP server expects a list of allowed directories as command-line arguments. It will only operate within these specified paths.

```bash
python3 main.py -d /path/to/allowed/dir1 /path/to/another/allowed/dir2 --log-level INFO --log-file mcp_server.log
```

**Arguments:**

  * `-d`, `--directories`: **(Required)** One or more paths to directories that the server is allowed to access. You can specify multiple directories.
  * `--log-file`: **(Optional)** Path to a file where server logs will be written. Logs will rotate to prevent excessive file size.
  * `--log-level`: **(Optional)** Minimum logging level to output. Choices are `DEBUG`, `INFO`, `WARNING`, `ERROR`. Default is `INFO`.

**Example:**

To allow the server access to your home directory's `projects` folder and a temporary `data` folder:

```bash
uv run main.py -d ~/projects /tmp/data --log-level DEBUG --log-file mcp_debug.log
```

Once running, the server will listen for MCP messages on its standard input (`stdin`) and respond on its standard output (`stdout`).

### Testing the Server with `test_mcp_server.py`

The `test_mcp_server.py` script is a utility for verifying the server's initialization and basic functionality. It launches the `main.py` server as a subprocess, sends an `initialize` MCP message, and captures the server's output and logs.

```bash
uv run test_mcp_server.py
```

This script will:

1.  Create a temporary directory (`~/mcp_test`) and a test file within it.
2.  Launch `main.py` as a subprocess, granting it access to the temporary directory.
3.  Send a standard MCP `initialize` request to the server.
4.  Monitor the server's output (`stdout`, `stderr`) for responses and errors.
5.  Print the server's debug log (`mcp_debug.log`) for detailed insights.
6.  Clean up the temporary test files and directories.

**Interpreting the Test Output:**

  * **`Response: {"jsonrpc": "2.0", "result": {}, "id": 1}`**: This indicates a successful MCP `initialize` response from your server, confirming it's correctly handling the initial handshake.
  * **`STDOUT` / `STDERR`**: Any direct print statements or uncaught exceptions from `main.py` will appear here. This is your first stop for runtime errors.
  * **`=== DEBUG LOG CONTENTS ===`**: Provides detailed logs from the server process itself. Look for messages indicating successful tool registration, path validation, and any errors during file operations.

-----

## Troubleshooting

If you encounter issues, here's a checklist:

1.  **Check Command Line Arguments**: Ensure you are providing at least one allowed directory to `main.py`. The server will not start without them.
2.  **`fastmcp` Installation**: Verify that the `fastmcp` library is correctly installed (`pip install fastmcp`).
3.  **Permissions**: Make sure the user running the server has read/write permissions for the specified allowed directories and the log file path.
4.  **Examine Logs (`mcp_debug.log`)**: The log file (especially with `--log-level DEBUG`) provides the most detailed information about what the server is doing and where it might be failing.
5.  **MCP Protocol Adherence**: Ensure your client is sending well-formed JSON-RPC 2.0 messages according to the MCP specification. The server expects messages on `stdin` and responds on `stdout`.
6.  **Path Validation Errors**: If you see "Access denied" errors, double-check that the requested paths fall strictly within the configured allowed directories. Remember that symlink targets are also validated.
7.  **`edit_file` Match Issues**: If `edit_file` reports that it "Could not find exact match," verify that the `oldText` in your edit operation exactly matches the content in the file, including whitespace and line endings.

-----

## Extending the Server

This server provides a solid foundation for filesystem interaction. You can extend its capabilities by:

  * **Adding More Tools**: Implement new `@mcp.tool()` functions for other filesystem operations (e.g., `copy_file`, `delete_file`, `checksum_file`).
  * **Integrating with Other Systems**: Modify tools to interact with cloud storage, databases, or version control systems, while still presenting a filesystem-like interface.
  * **Customizing Validation**: Enhance the `validate_path` function with more complex access control rules if needed.
