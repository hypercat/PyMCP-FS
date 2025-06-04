#!/usr/bin/env python3

import argparse
import os
import sys
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from datetime import datetime
import fnmatch
import difflib
import logging
from logging.handlers import RotatingFileHandler

from fastmcp import FastMCP

def setup_logging(log_file: Optional[str] = None, log_level: str = "INFO"):
    """Setup logging with optional file output
    
    Args:
        log_file (str, optional): Path to log file. Defaults to None.
        log_level (str, optional): Logging level. Defaults to "INFO".
    """
    handlers = []
    
    # Always log to stderr for MCP protocol compliance
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    handlers.append(stderr_handler)
    
    # Optional file logging
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use rotating file handler to prevent huge log files
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=1024*1024,  # 1MB
            backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        ))
        handlers.append(file_handler)
    
    # Set up root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        handlers=handlers,
        force=True
    )
    
    return logging.getLogger(__name__)

# Initialize logger (reconfigured in main)
logger = logging.getLogger(__name__)

def expand_home(filepath: str) -> str:
    """Expand ~ to home directory"""
    if filepath.startswith('~/') or filepath == '~':
        return os.path.join(os.path.expanduser('~'), filepath[1:].lstrip('/'))
    return filepath

def normalize_path(p: str) -> str:
    """Normalize path consistently"""
    return os.path.normpath(p)

def validate_allowed_directories(allowed_directories: List[str]):
    for _, dir_arg in enumerate(allowed_directories):
        expanded_dir = expand_home(dir_arg)
        if not os.path.exists(expanded_dir):
            logger.error(f"Directory {dir_arg} does not exist")
            sys.exit(1)
        if not os.path.isdir(expanded_dir):
            logger.error(f"{dir_arg} is not a directory")
            sys.exit(1)

@dataclass
class FileInfo:
    size: int
    created: datetime
    modified: datetime
    accessed: datetime
    is_directory: bool
    is_file: bool
    permissions: str

@dataclass
class TreeEntry:
    name: str
    type: str  # 'file' or 'directory'
    children: Optional[List['TreeEntry']] = None

@dataclass
class EditOperation:
    old_text: str
    new_text: str

allowed_directories: List[str] = []

async def validate_path(requested_path: str) -> str:
    """Validate that a path is within allowed directories
    
    Args:
        requested_path (str): Path to validate
    
    Returns:
        str: Validated path
    """
    expanded_path = expand_home(requested_path)
    absolute = os.path.abspath(expanded_path)
    normalized_requested = normalize_path(absolute)
    
    is_allowed = any(normalized_requested.startswith(dir) for dir in allowed_directories)
    if not is_allowed:
        raise ValueError(f"Access denied - path outside allowed directories: {absolute} not in {', '.join(allowed_directories)}")
    
    # Handle symlinks by checking their real path
    try:
        real_path = os.path.realpath(absolute)
        normalized_real = normalize_path(real_path)
        is_real_path_allowed = any(normalized_real.startswith(dir) for dir in allowed_directories)
        if not is_real_path_allowed:
            raise ValueError("Access denied - symlink target outside allowed directories")
        return real_path
    except OSError:
        # For new files that don't exist yet, verify parent directory
        parent_dir = os.path.dirname(absolute)
        try:
            real_parent_path = os.path.realpath(parent_dir)
            normalized_parent = normalize_path(real_parent_path)
            is_parent_allowed = any(normalized_parent.startswith(dir) for dir in allowed_directories)
            if not is_parent_allowed:
                raise ValueError("Access denied - parent directory outside allowed directories")
            return absolute
        except OSError:
            raise ValueError(f"Parent directory does not exist: {parent_dir}")

def normalize_line_endings(text: str) -> str:
    """Normalize line endings to \n"""
    return text.replace('\r\n', '\n')

def create_unified_diff(original_content: str, new_content: str, filepath: str = 'file') -> str:
    """Create a unified diff between two strings
    
    Args:
        original_content (str): Original string to diff against
        new_content (str): New string to diff
        filepath (str, optional): File path for diff header. Defaults to 'file'.
    
    Returns:
        str: Unified diff string
    """
    normalized_original = normalize_line_endings(original_content)
    normalized_new = normalize_line_endings(new_content)
    
    diff = difflib.unified_diff(
        normalized_original.splitlines(keepends=True),
        normalized_new.splitlines(keepends=True),
        fromfile=f"{filepath} (original)",
        tofile=f"{filepath} (modified)",
        lineterm=''
    )
    
    return ''.join(diff)

async def apply_file_edits(file_path: str, edits: List[EditOperation], dry_run: bool = False) -> str:
    """Apply edits to a file and return diff
    
    Args:
        file_path (str): Path to file to edit
        edits (List[EditOperation]): List of edit operations to apply
        dry_run (bool, optional): Whether to apply edits or not. Defaults to False.
    
    Returns:
        str: Unified diff string
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = normalize_line_endings(f.read())
    
    modified_content = content
    for edit in edits:
        normalized_old = normalize_line_endings(edit.old_text)
        normalized_new = normalize_line_endings(edit.new_text)
        

        if normalized_old in modified_content:
            modified_content = modified_content.replace(normalized_old, normalized_new, 1)
            continue
        
        # Otherwise, try line-by-line matching with flexibility for whitespace
        old_lines = normalized_old.split('\n')
        content_lines = modified_content.split('\n')
        match_found = False
        
        for i in range(len(content_lines) - len(old_lines) + 1):
            potential_match = content_lines[i:i + len(old_lines)]
            
            is_match = all(
                old_line.strip() == content_line.strip()
                for old_line, content_line in zip(old_lines, potential_match)
            )
            
            if is_match:
                original_indent = ''
                if content_lines[i]:
                    original_indent = content_lines[i][:len(content_lines[i]) - len(content_lines[i].lstrip())]
                
                new_lines = normalized_new.split('\n')
                for j, line in enumerate(new_lines):
                    if j == 0:
                        new_lines[j] = original_indent + line.lstrip()
                    else:
                        # For subsequent lines, try to preserve relative indentation
                        if j < len(old_lines):
                            old_indent = ''
                            if old_lines[j]:
                                old_indent = old_lines[j][:len(old_lines[j]) - len(old_lines[j].lstrip())]
                            new_indent = ''
                            if line:
                                new_indent = line[:len(line) - len(line.lstrip())]
                            
                            if old_indent and new_indent:
                                relative_indent = len(new_indent) - len(old_indent)
                                new_lines[j] = original_indent + ' ' * max(0, relative_indent) + line.lstrip()
                
                content_lines[i:i + len(old_lines)] = new_lines
                modified_content = '\n'.join(content_lines)
                match_found = True
                break
        
        if not match_found:
            raise ValueError(f"Could not find exact match for edit:\n{edit.old_text}")
    
    diff = create_unified_diff(content, modified_content, file_path)
    
    num_backticks = 3
    while '`' * num_backticks in diff:
        num_backticks += 1
    formatted_diff = f"{'`' * num_backticks}diff\n{diff}{'`' * num_backticks}\n\n"
    
    if not dry_run:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(modified_content)
    
    return formatted_diff

async def get_file_stats(file_path: str) -> FileInfo:
    """Get detailed file statistics
    
    Args:
        file_path (str): Path to file to get stats for
    
    Returns:
        FileInfo: Detailed file statistics
    """
    stat = os.stat(file_path)
    return FileInfo(
        size=stat.st_size,
        created=datetime.fromtimestamp(stat.st_ctime),
        modified=datetime.fromtimestamp(stat.st_mtime),
        accessed=datetime.fromtimestamp(stat.st_atime),
        is_directory=os.path.isdir(file_path),
        is_file=os.path.isfile(file_path),
        permissions=oct(stat.st_mode)[-3:]
    )

async def _search_files_impl(root_path: str, pattern: str, exclude_patterns: Optional[List[str]] = None) -> List[str]:
    """Recursively search for files matching a pattern
    
    Args:
        root_path (str): Root directory to search in
        pattern (str): Glob pattern to match
        exclude_patterns (Optional[List[str]], optional): List of glob patterns to exclude. Defaults to None.
    
    Returns:
        List[str]: List of matching file paths
    """
    if exclude_patterns is None:
        exclude_patterns = []
    
    results = []
    
    for root, dirs, files in os.walk(root_path):
        relative_root = os.path.relpath(root, root_path)
        
        should_exclude_dir = any(
            fnmatch.fnmatch(relative_root, f"**/{pattern}/**") or 
            fnmatch.fnmatch(relative_root, pattern if '*' in pattern else f"**/{pattern}/**")
            for pattern in exclude_patterns
        )
        
        if should_exclude_dir:
            dirs.clear()  # Don't recurse into excluded directories
            continue
        
        for item in dirs + files:
            full_path = os.path.join(root, item)
            
            try:
                await validate_path(full_path)
                
                relative_path = os.path.relpath(full_path, root_path)
                should_exclude = any(
                    fnmatch.fnmatch(relative_path, glob_pattern if '*' in exclude_pattern else f"**/{exclude_pattern}/**")
                    for exclude_pattern in exclude_patterns
                    for glob_pattern in [exclude_pattern]
                )
                
                if should_exclude:
                    continue
                
                if pattern.lower() in item.lower():
                    results.append(full_path)
                    
            except ValueError:
                continue
    
    return results

async def build_directory_tree(current_path: str) -> List[TreeEntry]:
    """Build a recursive tree structure of directories and files
    
    Args:
        current_path (str): Current directory to build tree from
    
    Returns:
        List[TreeEntry]: List of TreeEntry objects representing directories and files
    """
    valid_path = await validate_path(current_path)
    entries = []
    
    try:
        for item in os.listdir(valid_path):
            item_path = os.path.join(valid_path, item)
            
            if os.path.isdir(item_path):
                entry = TreeEntry(
                    name=item,
                    type='directory',
                    children=await build_directory_tree(item_path)
                )
            else:
                entry = TreeEntry(
                    name=item,
                    type='file'
                )
            
            entries.append(entry)
    except PermissionError:
        pass  # Skip directories we can't read
    
    return entries

logger.debug("Creating FastMCP server instance...")
mcp = FastMCP("Secure Filesystem Server")
logger.debug("FastMCP server instance created successfully")

@mcp.tool()
async def read_file(path: str) -> str:
    """Read the complete contents of a file from the file system.
    
    Handles various text encodings and provides detailed error messages
    if the file cannot be read. Use this tool when you need to examine
    the contents of a single file. Only works within allowed directories.

    Args:
        path (str): Path to the file to read

    Returns:
        str: The contents of the file
    """
    logger.debug(f"read_file called with path: {path}")
    valid_path = await validate_path(path)
    logger.debug(f"Path validated: {valid_path}")
    with open(valid_path, 'r', encoding='utf-8') as f:
        content = f.read()
    logger.debug(f"File read successfully, content length: {len(content)}")
    return content

@mcp.tool()
async def read_multiple_files(paths: List[str]) -> str:
    """Read the contents of multiple files simultaneously.
    
    This is more efficient than reading files one by one when you need to analyze
    or compare multiple files. Each file's content is returned with its
    path as a reference. Failed reads for individual files won't stop
    the entire operation. Only works within allowed directories.

    Args:
        paths (List[str]): List of file paths to read

    Returns:
        str: A string containing the contents of each file, separated by "---".
    """
    results = []
    
    for file_path in paths:
        try:
            valid_path = await validate_path(file_path)
            with open(valid_path, 'r', encoding='utf-8') as f:
                content = f.read()
            results.append(f"{file_path}:\n{content}\n")
        except Exception as e:
            results.append(f"{file_path}: Error - {str(e)}")
    
    return "\n---\n".join(results)

@mcp.tool()
async def write_file(path: str, content: str) -> str:
    """Create a new file or completely overwrite an existing file with new content.
    
    Use with caution as it will overwrite existing files without warning.
    Handles text content with proper encoding. Only works within allowed directories.

    Args:
        path (str): Path to the file to write
        content (str): The content to write to the file

    Returns:
        str: A message indicating success
    """
    valid_path = await validate_path(path)
    
    os.makedirs(os.path.dirname(valid_path), exist_ok=True)
    
    with open(valid_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return f"Successfully wrote to {path}"

@mcp.tool()
async def edit_file(path: str, edits: List[Dict[str, str]], dry_run: bool = False) -> str:
    """Make line-based edits to a text file.
    
    Each edit replaces exact line sequences with new content. Returns a git-style diff 
    showing the changes made. Only works within allowed directories.
    
    Args:
        path: Path to the file to edit
        edits: List of edits, each containing 'oldText' and 'newText' keys
        dry_run: Preview changes using git-style diff format without applying them

    Returns:
        str: A git-style diff showing the changes made
    """
    valid_path = await validate_path(path)
    
    edit_operations = [
        EditOperation(old_text=edit['oldText'], new_text=edit['newText'])
        for edit in edits
    ]
    
    return await apply_file_edits(valid_path, edit_operations, dry_run)

@mcp.tool()
async def create_directory(path: str) -> str:
    """Create a new directory or ensure a directory exists.
    
    Can create multiple nested directories in one operation. If the directory already exists,
    this operation will succeed silently. Perfect for setting up directory
    structures for projects or ensuring required paths exist. Only works within allowed directories.

    Args:
        path (str): Path to the directory to create

    Returns:
        str: A message indicating success
    """
    valid_path = await validate_path(path)
    os.makedirs(valid_path, exist_ok=True)
    return f"Successfully created directory {path}"

@mcp.tool()
async def list_directory(path: str) -> str:
    """Get a detailed listing of all files and directories in a specified path.
    
    Results clearly distinguish between files and directories with [FILE] and [DIR]
    prefixes. This tool is essential for understanding directory structure and
    finding specific files within a directory. Only works within allowed directories.

    Args:
        path (str): Path to the directory to list

    Returns:
        str: A newline-separated list of files and directories
    """
    valid_path = await validate_path(path)
    entries = []
    
    for item in os.listdir(valid_path):
        item_path = os.path.join(valid_path, item)
        if os.path.isdir(item_path):
            entries.append(f"[DIR] {item}")
        else:
            entries.append(f"[FILE] {item}")
    
    return "\n".join(entries)

@mcp.tool()
async def directory_tree(path: str) -> str:
    """Get a recursive tree view of files and directories as a JSON structure.
    
    Each entry includes 'name', 'type' (file/directory), and 'children' for directories.
    Files have no children array, while directories always have a children array (which may be empty).
    The output is formatted with 2-space indentation for readability. Only works within allowed directories.

    Args:
        path (str): Path to the directory to list

    Returns:
        str: A JSON string representing the directory tree
    """
    tree_data = await build_directory_tree(path)
    
    def tree_entry_to_dict(entry: TreeEntry) -> Dict[str, Union[str, List[Dict[str, Any]]]]:
        result: Dict[str, Union[str, List[Dict[str, Any]]]] = {
            "name": entry.name,
            "type": entry.type
        }
        if entry.children is not None:
            result["children"] = [tree_entry_to_dict(child) for child in entry.children]
        return result
    
    tree_dict = [tree_entry_to_dict(entry) for entry in tree_data]
    return json.dumps(tree_dict, indent=2)

@mcp.tool()
async def move_file(source: str, destination: str) -> str:
    """Move or rename files and directories.
    
    Can move files between directories and rename them in a single operation.
    If the destination exists, the operation will fail. Works across different directories
    and can be used for simple renaming within the same directory.
    Both source and destination must be within allowed directories.

    Args:
        source (str): Path to the file or directory to move
        destination (str): Path to the new location for the file or directory

    Returns:
        str: A message indicating success
    """
    valid_source_path = await validate_path(source)
    valid_dest_path = await validate_path(destination)
    
    os.makedirs(os.path.dirname(valid_dest_path), exist_ok=True)
    
    shutil.move(valid_source_path, valid_dest_path)
    return f"Successfully moved {source} to {destination}"

@mcp.tool()
async def search_files(path: str, pattern: str, exclude_patterns: Optional[List[str]] = None) -> str:
    """Recursively search for files and directories matching a pattern.
    
    Searches through all subdirectories from the starting path. The search
    is case-insensitive and matches partial names. Returns full paths to all
    matching items. Great for finding files when you don't know their exact location.
    Only searches within allowed directories.

    Args:
        path (str): Path to start the search from
        pattern (str): The search pattern to match
        exclude_patterns (Optional[List[str]]): A list of patterns to exclude from the search

    Returns:
        str: A newline-separated list of matching file and directory paths
    """
    if exclude_patterns is None:
        exclude_patterns = []
        
    valid_path = await validate_path(path)
    results = await _search_files_impl(valid_path, pattern, exclude_patterns)
    
    return "\n".join(results) if results else "No matches found"

@mcp.tool()
async def get_file_info(path: str) -> str:
    """Retrieve detailed metadata about a file or directory.
    
    Returns comprehensive information including size, creation time, last modified time,
    permissions, and type. This tool is perfect for understanding file characteristics
    without reading the actual content. Only works within allowed directories.

    Args:
        path (str): Path to the file or directory to get information about

    Returns:
        str: A newline-separated list of file information
    """
    valid_path = await validate_path(path)
    info = await get_file_stats(valid_path)
    
    return "\n".join([
        f"size: {info.size}",
        f"created: {info.created}",
        f"modified: {info.modified}",
        f"accessed: {info.accessed}",
        f"isDirectory: {info.is_directory}",
        f"isFile: {info.is_file}",
        f"permissions: {info.permissions}"
    ])

@mcp.tool()
async def list_allowed_directories() -> str:
    """Returns the list of directories that this server is allowed to access.
    
    Use this to understand which directories are available before trying to access files.
    
    Returns:
        str: A newline-separated list of allowed directories
    """
    logger.debug("list_allowed_directories called")
    return f"Allowed directories:\n{chr(10).join(allowed_directories)}"

# Log tool registration
logger.debug("All MCP tools registered successfully")
logger.debug("Available tools:")
for tool_name in ["read_file", "read_multiple_files", "write_file", "edit_file", 
                  "create_directory", "list_directory", "directory_tree", "move_file", 
                  "search_files", "get_file_info", "list_allowed_directories"]:
    logger.debug(f"  - {tool_name}")

def main():
    global allowed_directories
    
    # Parse command line arguments properly
    parser = argparse.ArgumentParser(description="Secure MCP Filesystem Server")
    parser.add_argument("-d", "--directories", nargs="+", help="List of allowed directories")
    parser.add_argument("--log-file", type=str, help="Optional log file path")
    parser.add_argument("--log-level", type=str, default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: INFO)")
    
    try:
        args = parser.parse_args()
        
        # Setup logging with optional file output
        global logger
        logger = setup_logging(args.log_file, args.log_level)
        
        logger.info("=== MCP Filesystem Server Starting ===")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Command line args: {sys.argv}")
        
        logger.info("Processing allowed directories...")
        allowed_directories = [normalize_path(os.path.abspath(expand_home(dir))) for dir in args.directories]
        logger.info(f"Allowed directories (normalized): {allowed_directories}")
        
        logger.info("Validating directories...")
        validate_allowed_directories(allowed_directories)
        logger.info("Directory validation completed successfully")
        
        # Log FastMCP version if possible
        try:
            import fastmcp
            logger.info(f"FastMCP version: {getattr(fastmcp, '__version__', 'unknown')}")
        except Exception as e:
            logger.warning(f"Could not determine FastMCP version: {e}")
        
        logger.info("Starting MCP server initialization...")
        logger.info("About to call mcp.run_async()...")
        
        logger.info("Calling mcp.run_async() - server should start accepting connections now")
        mcp.run()
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Server error during startup: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    try:
        logger.info("=== Starting MCP Server Process ===")
        main()
    except KeyboardInterrupt:
        logger.info("=== Server shutdown complete (KeyboardInterrupt) ===")
    except Exception as e:
        logger.error(f"=== Fatal error during server execution: {e} ===", exc_info=True)
        sys.exit(1)