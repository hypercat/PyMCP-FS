#!/usr/bin/env python3
"""Tests for tool behaviors that the tool docstrings promise.

These docstrings are what an MCP client model reads when deciding whether a
call is safe, so a mismatch between the text and the behavior is a defect in
its own right, not just stale documentation.
"""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
from main import build_directory_tree, canonical_path


def _tool(name):
    """Return the plain coroutine behind an @mcp.tool() wrapper."""
    attr = getattr(main, name)
    return getattr(attr, "fn", attr)


class TestToolContracts:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        main.allowed_directories = [canonical_path(self.temp_dir)]

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_move_file_refuses_existing_destination(self):
        """move_file documents that it fails if the destination exists."""
        source = os.path.join(self.temp_dir, "source.txt")
        destination = os.path.join(self.temp_dir, "destination.txt")
        with open(source, "w") as f:
            f.write("source content")
        with open(destination, "w") as f:
            f.write("destination content")

        with pytest.raises(ValueError, match="already exists"):
            await _tool("move_file")(source, destination)

        # Neither side may be disturbed by the refused move.
        with open(destination) as f:
            assert f.read() == "destination content"
        assert os.path.exists(source)

    @pytest.mark.asyncio
    async def test_move_file_still_moves_to_a_free_destination(self):
        """The guard must not block the ordinary case."""
        source = os.path.join(self.temp_dir, "source.txt")
        destination = os.path.join(self.temp_dir, "moved.txt")
        with open(source, "w") as f:
            f.write("source content")

        await _tool("move_file")(source, destination)

        assert not os.path.exists(source)
        with open(destination) as f:
            assert f.read() == "source content"

    @pytest.mark.asyncio
    async def test_read_file_reports_undecodable_files_clearly(self):
        """A binary file must raise a descriptive error, not UnicodeDecodeError."""
        binary = os.path.join(self.temp_dir, "data.bin")
        with open(binary, "wb") as f:
            f.write(bytes(range(256)))

        with pytest.raises(ValueError, match="UTF-8"):
            await _tool("read_file")(binary)

    @pytest.mark.asyncio
    async def test_read_file_still_reads_text(self):
        """The error handling must not disturb ordinary text reads."""
        text = os.path.join(self.temp_dir, "note.txt")
        with open(text, "w", encoding="utf-8") as f:
            f.write("hello, world")

        assert await _tool("read_file")(text) == "hello, world"

    @pytest.mark.asyncio
    async def test_directory_tree_terminates_on_symlink_cycle(self):
        """A symlink pointing at an ancestor must not recurse without bound."""
        nested = os.path.join(self.temp_dir, "nested")
        os.makedirs(nested, exist_ok=True)
        try:
            os.symlink(self.temp_dir, os.path.join(nested, "loop"),
                       target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError):
            pytest.skip("Symlinks not supported on this system")

        # Completing at all is the assertion: before the cycle guard this
        # recursed until the interpreter ran out of stack.
        tree = await build_directory_tree(self.temp_dir)
        assert any(entry.name == "nested" for entry in tree)
