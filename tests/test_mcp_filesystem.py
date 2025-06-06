#!/usr/bin/env python3

import pytest
import asyncio
import os
import tempfile
import shutil
import json
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Import the main module
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
from main import (
    validate_path, expand_home, normalize_path, validate_allowed_directories,
    apply_file_edits, EditOperation, get_file_stats, build_directory_tree,
    create_unified_diff, normalize_line_endings, setup_logging
)

class TestPathValidation:
    """Tests für Pfad-Validierung und Sicherheit"""

    def setup_method(self):
        """Setup für jeden Test"""
        self.temp_dir = tempfile.mkdtemp()
        self.allowed_dir = os.path.join(self.temp_dir, "allowed")
        os.makedirs(self.allowed_dir, exist_ok=True)

        # Set allowed directories globally
        main.allowed_directories = [normalize_path(os.path.abspath(self.allowed_dir))]

    def teardown_method(self):
        """Cleanup nach jedem Test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_expand_home(self):
        """Test home directory expansion"""
        # Test with tilde
        result = expand_home("~/test")
        expected = os.path.join(os.path.expanduser('~'), "test")
        assert result == expected

        # Test without tilde
        result = expand_home("/absolute/path")
        assert result == "/absolute/path"

        # Test with just tilde
        result = expand_home("~")
        assert result == os.path.expanduser('~')

    def test_normalize_path(self):
        """Test path normalization"""
        test_path = "some//path/../normalized"
        result = normalize_path(test_path)
        expected = os.path.normpath(test_path)
        assert result == expected

    @pytest.mark.asyncio
    async def test_validate_path_allowed(self):
        """Test validation of allowed paths"""
        test_file = os.path.join(self.allowed_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")

        result = await validate_path(test_file)
        assert os.path.samefile(result, test_file)

    @pytest.mark.asyncio
    async def test_validate_path_denied(self):
        """Test validation rejects paths outside allowed directories"""
        forbidden_path = os.path.join(self.temp_dir, "forbidden", "test.txt")
        os.makedirs(os.path.dirname(forbidden_path), exist_ok=True)

        with pytest.raises(ValueError, match="Access denied"):
            await validate_path(forbidden_path)

    @pytest.mark.asyncio
    async def test_validate_path_symlink_allowed(self):
        """Test validation of symlinks pointing to allowed directories"""
        target_file = os.path.join(self.allowed_dir, "target.txt")
        with open(target_file, 'w') as f:
            f.write("target content")

        symlink_path = os.path.join(self.allowed_dir, "symlink.txt")
        try:
            os.symlink(target_file, symlink_path)
            result = await validate_path(symlink_path)
            assert os.path.samefile(result, target_file)
        except OSError:
            # Skip test if symlinks not supported
            pytest.skip("Symlinks not supported on this system")

    def test_validate_allowed_directories_valid(self):
        """Test validation of existing directories"""
        # Should not raise exception
        validate_allowed_directories([self.allowed_dir])

    def test_validate_allowed_directories_invalid(self):
        """Test validation rejects non-existent directories"""
        with pytest.raises(SystemExit):
            validate_allowed_directories(["/non/existent/path"])


class TestFileOperations:
    """Tests für Datei-Operationen"""

    def setup_method(self):
        """Setup für jeden Test"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = os.path.join(self.temp_dir, "test")
        os.makedirs(self.test_dir, exist_ok=True)

        # Set allowed directories globally
        main.allowed_directories = [normalize_path(os.path.abspath(self.temp_dir))]

    def teardown_method(self):
        """Cleanup nach jedem Test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_normalize_line_endings(self):
        """Test line ending normalization"""
        text_with_crlf = "line1\r\nline2\r\nline3"
        result = normalize_line_endings(text_with_crlf)
        expected = "line1\nline2\nline3"
        assert result == expected

    def test_create_unified_diff(self):
        """Test unified diff creation"""
        original = "line1\nline2\nline3"
        modified = "line1\nmodified line2\nline3"

        diff = create_unified_diff(original, modified, "test.txt")

        assert "test.txt (original)" in diff
        assert "test.txt (modified)" in diff
        assert "-line2" in diff
        assert "+modified line2" in diff

    @pytest.mark.asyncio
    async def test_apply_file_edits(self):
        """Test file editing functionality"""
        test_file = os.path.join(self.test_dir, "edit_test.txt")
        original_content = "line1\nline2\nline3"

        with open(test_file, 'w') as f:
            f.write(original_content)
                                                                                                                                                                                                                            
        edits = [EditOperation(old_text="line2", new_text="modified line2")]
        diff = await apply_file_edits(test_file, edits, dry_run=False)
                                                                                                                                                                                                                            
        # Check that diff was generated
        assert "diff" in diff
        assert "-line2" in diff
        assert "+modified line2" in diff

        # Check that file was actually modified
        with open(test_file, 'r') as f:
            content = f.read()
        assert "modified line2" in content

    @pytest.mark.asyncio
    async def test_apply_file_edits_dry_run(self):
        """Test file editing in dry run mode"""
        test_file = os.path.join(self.test_dir, "dry_run_test.txt")
        original_content = "line1\nline2\nline3"

        with open(test_file, 'w') as f:
            f.write(original_content)

        edits = [EditOperation(old_text="line2", new_text="modified line2")]
        diff = await apply_file_edits(test_file, edits, dry_run=True)

        # Check that diff was generated
        assert "diff" in diff

        # Check that file was NOT modified
        with open(test_file, 'r') as f:
            content = f.read()
        assert content == original_content

    @pytest.mark.asyncio
    async def test_get_file_stats(self):
        """Test file statistics retrieval"""
        test_file = os.path.join(self.test_dir, "stats_test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")

        stats = await get_file_stats(test_file)

        assert stats.size > 0
        assert stats.is_file is True
        assert stats.is_directory is False
        assert stats.permissions is not None

    @pytest.mark.asyncio
    async def test_build_directory_tree(self):
        """Test directory tree building"""
        # Create test structure
        subdir = os.path.join(self.test_dir, "subdir")
        os.makedirs(subdir)

        with open(os.path.join(self.test_dir, "file1.txt"), 'w') as f:
            f.write("content1")
        with open(os.path.join(subdir, "file2.txt"), 'w') as f:
            f.write("content2")

        tree = await build_directory_tree(self.test_dir)

        # Should have 2 entries: file1.txt and subdir
        assert len(tree) == 2

        # Find the file and directory entries
        file_entry = next((e for e in tree if e.name == "file1.txt"), None)
        dir_entry = next((e for e in tree if e.name == "subdir"), None)

        assert file_entry is not None
        assert file_entry.type == "file"
        assert file_entry.children is None
                                                                                                                                                                                                                            
        assert dir_entry is not None
        assert dir_entry.type == "directory"
        assert dir_entry.children is not None
        assert len(dir_entry.children) == 1
        assert dir_entry.children[0].name == "file2.txt"

                                                                                                                                                                                                                            
class TestMCPTools:
    """Tests für MCP Tool-Funktionen"""

    def setup_method(self):
        """Setup für jeden Test"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = os.path.join(self.temp_dir, "test")
        os.makedirs(self.test_dir, exist_ok=True)

        # Set allowed directories globally
        main.allowed_directories = [normalize_path(os.path.abspath(self.temp_dir))]

    def teardown_method(self):
        """Cleanup nach jedem Test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_read_file_tool(self):
        """Test read_file MCP tool"""
        test_file = os.path.join(self.test_dir, "read_test.txt")
        test_content = "Hello, World!"

        with open(test_file, 'w') as f:
            f.write(test_content)
                                                                                                                                                                                                                            
        # Import the tool function directly
        from main import read_file
        result = await read_file(test_file)
        assert result == test_content

    @pytest.mark.asyncio
    async def test_write_file_tool(self):
        """Test write_file MCP tool"""
        test_file = os.path.join(self.test_dir, "write_test.txt")
        test_content = "Written content"
                                                                                                                                                                                                                            
        # Import the tool function directly
        from main import write_file
        result = await write_file(test_file, test_content)

        assert "Successfully wrote" in result

        # Verify file was created with correct content
        with open(test_file, 'r') as f:
            content = f.read()
        assert content == test_content

    @pytest.mark.asyncio
    async def test_list_directory_tool(self):
        """Test list_directory MCP tool"""
        # Create test files and directories
        with open(os.path.join(self.test_dir, "file1.txt"), 'w') as f:
            f.write("content1")
        os.makedirs(os.path.join(self.test_dir, "subdir"))

        # Import the tool function directly
        from main import list_directory
        result = await list_directory(self.test_dir)

        assert "[FILE] file1.txt" in result
        assert "[DIR] subdir" in result
                                                                                                                                                                                                                            
    @pytest.mark.asyncio
    async def test_create_directory_tool(self):
        """Test create_directory MCP tool"""
        new_dir = os.path.join(self.test_dir, "new_directory")

        # Import the tool function directly
        from main import create_directory
        result = await create_directory(new_dir)

        assert "Successfully created" in result
        assert os.path.isdir(new_dir)

    @pytest.mark.asyncio
    async def test_search_files_tool(self):
        """Test search_files MCP tool"""
        # Create test files
        with open(os.path.join(self.test_dir, "search_me.txt"), 'w') as f:
            f.write("content")
        with open(os.path.join(self.test_dir, "other.txt"), 'w') as f:
            f.write("content")
                                                                                                                                                                                                                            
        # Import the tool function directly
        from main import search_files
        result = await search_files(self.test_dir, "search")
                                                                                                                                                                                                                            
        assert "search_me.txt" in result
        assert "other.txt" not in result
                                                                                                                                                                                                                            
    @pytest.mark.asyncio
    async def test_list_allowed_directories_tool(self):
        """Test list_allowed_directories MCP tool"""
        # Import the tool function directly
        from main import list_allowed_directories
        result = await list_allowed_directories()

        assert "Allowed directories:" in result
        assert self.temp_dir in result

                                                                                                                                                                                                                            
class TestLogging:
    """Tests für Logging-Funktionalität"""
                                                                                                                                                                                                                            
    def test_setup_logging_stderr_only(self):
        """Test logging setup with stderr only"""
        logger = setup_logging(log_level="DEBUG")
        assert logger is not None
        assert logger.level <= 10  # DEBUG level

    def test_setup_logging_with_file(self):
        """Test logging setup with file output"""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            logger = setup_logging(log_file=log_file, log_level="INFO")

            assert logger is not None
            logger.info("Test message")
                                                                                                                                                                                                                            
            # Check that log file was created
            assert os.path.exists(log_file)
            
            # Close all handlers to release file handles on Windows
            for handler in logger.handlers[:]:
                handler.close()
                logger.removeHandler(handler)
            
            # Also close handlers on root logger
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                if hasattr(handler, 'baseFilename') and handler.baseFilename == log_file:
                    handler.close()
                    root_logger.removeHandler(handler)
                                                                                                                                                                                                                            
                                                                                                                                                                                                                            
class TestMainFunction:
    """Tests für main() Funktion"""

    def test_main_with_invalid_directory(self):
        """Test main function with invalid directory"""
        with patch('sys.argv', ['main.py', '--directories', '/non/existent/path']):
            with pytest.raises(SystemExit):
                main.main()

    @patch('main.mcp.run')
    def test_main_with_valid_directory(self, mock_run):
        """Test main function with valid directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('sys.argv', ['main.py', '--directories', temp_dir]):
                try:
                    main.main()
                    mock_run.assert_called_once()
                except SystemExit:
                    # Expected if mcp.run() raises SystemExit
                    pass
                                                                                                                                                                                                                            
                                                                                                                                                                                                                            
def test_mcp_server():
    """Haupttest-Funktion für Kompatibilität"""
    # Run a subset of critical tests
    test_instance = TestPathValidation()
    test_instance.setup_method()
    try:
        test_instance.test_normalize_path()
        # Skip test_expand_home since it's tested separately
    finally:
        test_instance.teardown_method()
                                                                                                                                                                                                                            
    print("MCP Server tests completed successfully!")
                                                                                                                                                                                                                            

if __name__ == "__main__":
    # Run tests with pytest if available, otherwise run basic test
    try:
        pytest.main([__file__, "-v"])
    except ImportError:
        test_mcp_server() 
