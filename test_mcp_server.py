#!/usr/bin/env python3
"""
Simple test script to debug PyMCP-FS server initialization issues.
This script will help identify where the server is getting stuck, if so.
"""

import subprocess
import sys
import time
import json
import os
from pathlib import Path

def test_mcp_server():
    """Test the MCP server by launching it and sending an initialize message"""
    
    # Create a temporary directory for testing
    test_dir = Path.home() / "mcp_test"
    test_dir.mkdir(exist_ok=True)
    
    # Create a test file
    test_file = test_dir / "test.txt"
    test_file.write_text("Hello, MCP!")
    
    print(f"Testing MCP server with directory: {test_dir}")
    
    # Launch the MCP server
    cmd = [
        sys.executable, 
        "main.py",
        str(test_dir),
        "--log-level", "DEBUG",
        "--log-file", "mcp_debug.log"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    
    try:
        # Start the server process
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        
        print("Server process started, PID:", process.pid)
        
        # Send initialize message
        initialize_message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {
                        "listChanged": True
                    },
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        print("Sending initialize message...")
        message_str = json.dumps(initialize_message) + "\n"
        print(f"Message: {message_str}")
        
        # Send the message
        process.stdin.write(message_str)
        process.stdin.flush()
        
        print("Message sent, waiting for response...")
        
        # Wait for response with timeout
        start_time = time.time()
        timeout = 10  # 10 seconds
        
        while time.time() - start_time < timeout:
            if process.poll() is not None:
                print(f"Process exited with code: {process.returncode}")
                break
                
            # Try to read response
            try:
                # Check if there's output available
                import select
                ready, _, _ = select.select([process.stdout], [], [], 1)
                if ready:
                    response = process.stdout.readline()
                    if response:
                        print(f"Response: {response.strip()}")
                        break
            except:
                # Fallback for Windows
                time.sleep(1)
                continue
        
        # Get any remaining output
        stdout, stderr = process.communicate(timeout=5)
        
        if stdout:
            print(f"STDOUT:\n{stdout}")
        if stderr:
            print(f"STDERR:\n{stderr}")
            
        # Check log file
        if os.path.exists("mcp_debug.log"):
            print("\n=== DEBUG LOG CONTENTS ===")
            with open("mcp_debug.log", "r") as f:
                print(f.read())
        
        # Cleanup
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
            
    except Exception as e:
        print(f"Error testing server: {e}")
        if 'process' in locals():
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                pass
    
    # Cleanup test files
    try:
        test_file.unlink(missing_ok=True)
        test_dir.rmdir()
    except:
        pass

if __name__ == "__main__":
    test_mcp_server()