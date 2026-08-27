#!/usr/bin/env python3
"""Integration checks for server startup and the MCP initialize handshake.

Runnable directly as a debugging aid (`uv run test_mcp_server.py`) and collected
by pytest as a real test. It launches main.py as a subprocess the way an MCP
client would, performs the initialize handshake over stdio, and asserts on the
response instead of only printing it.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
TIMEOUT_SECONDS = 30


def _run_server(args, stdin_text=""):
    """Launch main.py with the given arguments, feed it stdin, and let it exit.

    Closing stdin ends the stdio session, so the server shuts down on its own.
    communicate() is used rather than select(), which does not work on Windows
    pipes.
    """
    process = subprocess.Popen(
        [sys.executable, str(REPO_ROOT / "main.py")] + args,
        cwd=str(REPO_ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(stdin_text, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        raise AssertionError(
            "server did not exit within %ds; stdout so far: %r"
            % (TIMEOUT_SECONDS, stdout[:500])
        )
    return process.returncode, stdout, stderr


def test_initialize_handshake():
    """The server answers a JSON-RPC initialize request and then exits cleanly."""
    with tempfile.TemporaryDirectory() as allowed_dir:
        (Path(allowed_dir) / "test.txt").write_text("Hello, MCP!", encoding="utf-8")

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }
        code, stdout, stderr = _run_server(
            ["-d", allowed_dir, "--log-level", "ERROR"],
            json.dumps(request) + "\n",
        )

        # Printed so a direct run stays useful for debugging; pytest shows this
        # only when the test fails.
        print("STDOUT:\n%s" % stdout)
        print("STDERR:\n%s" % stderr)

        assert stdout.strip(), "server produced no response on stdout"
        response = json.loads(stdout.splitlines()[0])
        assert response.get("jsonrpc") == "2.0"
        assert response.get("id") == 1
        assert "result" in response, "expected a result, got %r" % response
        assert "serverInfo" in response["result"]
        assert "tools" in response["result"]["capabilities"]
        assert code == 0, "server exited with code %d" % code


def test_missing_directories_argument_is_rejected():
    """Omitting --directories gives an argparse usage error, not a traceback."""
    code, _, stderr = _run_server([])
    assert code != 0, "server should refuse to start without allowed directories"
    assert "the following arguments are required" in stderr.lower()
    assert "Traceback" not in stderr


if __name__ == "__main__":
    test_initialize_handshake()
    test_missing_directories_argument_is_rejected()
    print("PyMCP-FS server integration checks passed.")
