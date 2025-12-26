"""
UI Capabilities Test
====================

Tests to verify Chrome DevTools MCP integration works correctly.
These tests ensure the agent can perform browser automation.

Note: These tests require Chrome to be installed and chrome-devtools-mcp
to be available via npx. They are primarily for manual verification
and CI environments with browser support.
"""

import unittest
import subprocess
import json
import sys


class TestUICapabilities(unittest.TestCase):
    """Test browser automation capabilities."""

    def test_chrome_devtools_mcp_available(self):
        """Verify chrome-devtools-mcp package is accessible via npx."""
        # Check if npx can find the package (doesn't actually run it)
        result = subprocess.run(
            ["npm", "show", "chrome-devtools-mcp", "version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, "chrome-devtools-mcp package not found on npm")
        self.assertTrue(len(result.stdout.strip()) > 0, "No version returned")

    def test_browser_tools_defined_in_client(self):
        """Verify BROWSER_TOOLS list is properly defined in client.py."""
        # Import the module to check the tools list
        sys.path.insert(0, ".")
        from client import BROWSER_TOOLS

        # Check essential tools are present
        essential_tools = [
            "mcp__chrome-devtools__navigate_page",
            "mcp__chrome-devtools__take_screenshot",
            "mcp__chrome-devtools__click",
            "mcp__chrome-devtools__fill",
        ]
        
        for tool in essential_tools:
            self.assertIn(tool, BROWSER_TOOLS, f"Missing essential tool: {tool}")

    def test_mcp_server_config_in_client(self):
        """Verify MCP server is configured correctly in client.py."""
        with open("client.py", "r") as f:
            content = f.read()
        
        # Check that chrome-devtools-mcp is configured
        self.assertIn("chrome-devtools-mcp", content, "chrome-devtools-mcp not configured")
        self.assertIn("chrome-devtools", content, "chrome-devtools server not defined")
        
        # Ensure old puppeteer-mcp-server is not present
        self.assertNotIn("puppeteer-mcp-server", content, "Old puppeteer-mcp-server still configured")


if __name__ == "__main__":
    unittest.main()
