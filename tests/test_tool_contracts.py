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
from main import canonical_path


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
