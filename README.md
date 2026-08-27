# Python (MCP) Filesystem Server

This repository contains a robust Python-based **Model Context Protocol (MCP) Filesystem Server**. It enables AI models and applications to securely interact with the host system's file directories through a defined set of tools, allowing for operations like reading, writing, moving, and listing files and directories.

The server is built upon the `fastmcp` library and adheres to the [Model Context Protocol](https://github.com/modelcontextprotocol), providing a standardized way for AI tools to manage and access files within specified boundaries.

It's inspired by this [example typescript implementation](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem).

-----

## Features

  * **Secure Directory Access:** All file operations are strictly confined to a predefined list of allowed directories, preventing unauthorized access to other parts of the filesystem.
  * **Comprehensive File Operations:**
      * **`read_file`**: Read the complete contents of a single UTF-8 text file. Files that are not valid UTF-8, such as binaries, are reported as an error rather than returned as mojibake.
      * **`read_multiple_files`**: Efficiently read content from multiple files, returning results with clear path references.
      * **`write_file`**: Create new files or overwrite existing ones with specified content.
      * **`edit_file`**: Apply line-based edits to text files, with an option for a dry run to preview changes as a Git-style diff.
      * **`create_directory`**: Create new directories, including nested structures, or ensure their existence.
      * **`list_directory`**: Get a detailed listing of files and subdirectories within a given path.
      * **`directory_tree`**: Generate a recursive JSON tree structure of files and directories for a clear hierarchical view.
      * **`move_file`**: Move or rename files and directories. Refuses to overwrite an existing destination.
      * **`search_files`**: Recursively search for files and directories matching a pattern, with optional exclusion patterns.
      * **`get_file_info`**: Retrieve detailed metadata (size, timestamps, permissions) about files or directories. On Linux the reported creation time is the inode change time, which is all the platform exposes.
  * **Dynamic Allowed Directories:** Configurable via command-line arguments to specify exactly which directories the server can access.
  * **Robust Logging:** Integrates comprehensive logging with support for different log levels and output to both `stderr` (for MCP compliance) and an optional rotating log file.
  * **Error Handling:** Provides detailed error messages for common issues like access denied, file not found, or permission errors.
  * **Line Ending Normalization:** Handles `\r\n` and `\n` line endings consistently for `edit_file` operations.
  * **Path Canonicalization:** Requested paths and allowed directories are both fully resolved before the containment check, so symlinks, `..` segments and Windows 8.3 short names can neither escape the allowed tree nor cause a legitimate path inside it to be rejected.

-----

## Getting Started

### Prerequisites

  * **Python 3.10+**: Matches `requires-python` in `pyproject.toml`. CI covers 3.10, 3.12 and 3.13 on both Linux and Windows.
  * **`fastmcp` library**: This server uses the `fastmcp` library for MCP protocol handling. You'll need to install it.

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/hypercat/PyMCP-FS.git
    cd PyMCP-FS
    ```

2.  **Install dependencies with `uv`:**

    ```bash
    uv sync
    ```

    This installs from `uv.lock`, so you get the same versions CI tests against. Pass `--no-dev` to skip the test tooling.

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

### Running the tests

The suite covers path validation and confinement, the file operation helpers,
the MCP tool functions, and server startup.

```bash
uv sync
uv run pytest
```

`tests/test_path_confinement.py` covers the allowed-directory boundary
specifically, including the sibling-prefix and aliased-directory cases.

`test_mcp_server.py` doubles as an integration check and a debugging aid. It
launches `main.py` as a subprocess, performs the MCP `initialize` handshake
over stdio, and asserts on the response. Run it on its own to see the whole
exchange printed:

```bash
uv run test_mcp_server.py
```

CI runs the full suite on Linux and Windows across Python 3.10, 3.12 and 3.13.
A pull request cannot be merged unless every job passes.

-----

## Troubleshooting

If you encounter issues, here's a checklist:

1.  **Check Command Line Arguments**: Ensure you are providing at least one allowed directory to `main.py`. The server will not start without them.
2.  **Dependencies**: Verify the environment is in sync with the lockfile (`uv sync`).
3.  **Permissions**: Make sure the user running the server has read/write permissions for the specified allowed directories and the log file path.
4.  **Examine Logs (`mcp_debug.log`)**: The log file (especially with `--log-level DEBUG`) provides the most detailed information about what the server is doing and where it might be failing.
5.  **MCP Protocol Adherence**: Ensure your client is sending well-formed JSON-RPC 2.0 messages according to the MCP specification. The server expects messages on `stdin` and responds on `stdout`.
6.  **Path Validation Errors**: If you see "Access denied" errors, double-check that the requested paths fall strictly within the configured allowed directories. Paths are compared after full resolution, so a symlink is judged by its target, not by where the link sits.
7.  **`edit_file` Match Issues**: If `edit_file` reports that it "Could not find exact match," verify that the `oldText` in your edit operation exactly matches the content in the file, including whitespace and line endings.

-----

## Security

Every file operation is confined to the directories passed via `--directories`.
Requested paths and allowed directories are both fully resolved before the
containment check, so symlinks, `..` segments and Windows 8.3 short names
cannot be used to step outside the allowed tree.

That confinement is the security property this project cares about. If you find
a way around it, please report it privately rather than opening an issue. See
[SECURITY.md](SECURITY.md) for the reporting channel and scope.

The boundary is only ever as tight as what you allow. Pointing the server at a
sensitive directory, or at `/`, grants the connected model exactly that access.

-----

## Extending the Server

This server provides a solid foundation for filesystem interaction. You can extend its capabilities by:

  * **Adding More Tools**: Implement new `@mcp.tool()` functions for other filesystem operations (e.g., `copy_file`, `delete_file`, `checksum_file`).
  * **Integrating with Other Systems**: Modify tools to interact with cloud storage, databases, or version control systems, while still presenting a filesystem-like interface.
  * **Customizing Validation**: Enhance the `validate_path` function with more complex access control rules if needed.

-----

## License

Released under the [BSD Zero Clause License](LICENSE) (0BSD), the most
permissive license approved by the Open Source Initiative. You may use, modify
and redistribute this software for any purpose, with no obligation to preserve
a copyright notice or to ship the license text.
