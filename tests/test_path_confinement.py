#!/usr/bin/env python3
"""Regression tests for allowed-directory confinement in validate_path.

Covers the sibling-prefix bypass: before the boundary-aware containment check,
validate_path compared paths with a bare str.startswith() against allowed
directory entries that carry no trailing separator. A sibling directory whose
name merely extends the allowed directory's name (allowed_secret against an
allowed allowed) therefore satisfied the check, and every path-taking tool
would read from and write to it.
"""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main
from main import is_within_allowed, normalize_path, validate_path


class TestSiblingPrefixConfinement:
    """Out-of-tree paths must be rejected even when they share the allowed prefix."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.allowed_dir = os.path.join(self.temp_dir, "allowed")
        os.makedirs(self.allowed_dir, exist_ok=True)
        main.allowed_directories = [normalize_path(os.path.abspath(self.allowed_dir))]

    def teardown_method(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_sibling_sharing_prefix_is_denied(self):
        """A sibling whose name extends the allowed directory's name is out of tree."""
        sibling_dir = self.allowed_dir + "_secret"
        os.makedirs(sibling_dir, exist_ok=True)
        sibling_file = os.path.join(sibling_dir, "creds.txt")
        with open(sibling_file, "w") as f:
            f.write("secret content")

        with pytest.raises(ValueError, match="Access denied"):
            await validate_path(sibling_file)

    @pytest.mark.asyncio
    async def test_sibling_sharing_prefix_new_file_is_denied(self):
        """A not-yet-existing file inside a prefix-sharing sibling must be rejected."""
        sibling_dir = self.allowed_dir + "-backup"
        os.makedirs(sibling_dir, exist_ok=True)

        with pytest.raises(ValueError, match="Access denied"):
            await validate_path(os.path.join(sibling_dir, "planted.txt"))

    @pytest.mark.asyncio
    async def test_traversal_into_sibling_is_denied(self):
        """A .. segment normalizing into a prefix-sharing sibling is still out of tree."""
        sibling_dir = self.allowed_dir + "_secret"
        os.makedirs(sibling_dir, exist_ok=True)
        sibling_file = os.path.join(sibling_dir, "creds.txt")
        with open(sibling_file, "w") as f:
            f.write("secret content")

        traversal = os.path.join(self.allowed_dir, "..", "allowed_secret", "creds.txt")
        with pytest.raises(ValueError, match="Access denied"):
            await validate_path(traversal)

    @pytest.mark.asyncio
    async def test_file_inside_allowed_directory_still_works(self):
        """The boundary check must not deny legitimate in-tree access."""
        test_file = os.path.join(self.allowed_dir, "ok.txt")
        with open(test_file, "w") as f:
            f.write("in-tree content")

        result = await validate_path(test_file)
        assert os.path.samefile(result, test_file)


class TestIsWithinAllowed:
    """Unit coverage for the containment helper itself."""

    def setup_method(self):
        self.allowed = os.path.join(os.sep, "home", "u", "project")

    def test_sibling_prefix_not_contained(self):
        sibling = os.path.join(os.sep, "home", "u", "project-backup", "f.txt")
        assert not is_within_allowed(sibling, [self.allowed])

    def test_descendant_contained(self):
        child = os.path.join(self.allowed, "f.txt")
        assert is_within_allowed(child, [self.allowed])

    def test_directory_itself_contained(self):
        assert is_within_allowed(self.allowed, [self.allowed])

    def test_unrelated_path_not_contained(self):
        unrelated = os.path.join(os.sep, "etc", "passwd")
        assert not is_within_allowed(unrelated, [self.allowed])
