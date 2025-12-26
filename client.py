"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
"""

import json
import os
from pathlib import Path

# NOTE: Imports are lazy-loaded in create_client to avoid hard dependency on SDK
# from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
# from claude_code_sdk.types import HookMatcher

from security import bash_security_hook


# Chrome DevTools MCP tools for browser automation
# See: https://github.com/anthropics/anthropic-quickstarts/tree/main/mcp-servers/chrome-devtools
BROWSER_TOOLS = [
    "mcp__chrome-devtools__navigate_page",
    "mcp__chrome-devtools__take_screenshot",
    "mcp__chrome-devtools__click",
    "mcp__chrome-devtools__fill",
    "mcp__chrome-devtools__hover",
    "mcp__chrome-devtools__take_snapshot",
    "mcp__chrome-devtools__evaluate_script",
    "mcp__chrome-devtools__list_pages",
    "mcp__chrome-devtools__select_page",
    "mcp__chrome-devtools__new_page",
    "mcp__chrome-devtools__close_page",
    "mcp__chrome-devtools__list_console_messages",
    "mcp__chrome-devtools__list_network_requests",
]

# Built-in tools
BUILTIN_TOOLS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]


def create_client(project_dir: Path, model: str) -> "ClaudeSDKClient":
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use

    Returns:
        Configured ClaudeSDKClient

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
    2. Permissions - File operations restricted to project_dir only
    3. Security hooks - Bash commands validated against an allowlist
       (see security.py for ALLOWED_COMMANDS)
    """
    from claude_code_sdk import ClaudeCodeOptions, ClaudeSDKClient
    from claude_code_sdk.types import HookMatcher

    oauth_token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not oauth_token and not api_key:
        raise ValueError(
            "Authentication not configured. Set one of:\n"
            "- CLAUDE_CODE_OAUTH_TOKEN (run `claude setup-token`)\n"
            "- ANTHROPIC_API_KEY"
        )

    # Create comprehensive security settings
    # Note: Using relative paths ("./**") restricts access to project directory
    # since cwd is set to project_dir
    security_settings = {
        "sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True},
        "permissions": {
            "defaultMode": "acceptEdits",  # Auto-approve edits within allowed directories
            "allow": [
                # Allow all file operations within the project directory
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                # Bash permission granted here, but actual commands are validated
                # by the bash_security_hook (see security.py for allowed commands)
                "Bash(*)",
                # Allow Chrome DevTools MCP tools for browser automation
                *BROWSER_TOOLS,
            ],
        },
    }

    # Ensure project directory exists before creating settings file
    project_dir.mkdir(parents=True, exist_ok=True)

    # Write settings to a file in the project directory
    settings_file = project_dir / ".claude_settings.json"
    with open(settings_file, "w") as f:
        json.dump(security_settings, f, indent=2)

    print(f"Created security settings at {settings_file}")
    print("   - Sandbox enabled (OS-level bash isolation)")
    print(f"   - Filesystem restricted to: {project_dir.resolve()}")
    print("   - Bash commands restricted to allowlist (see security.py)")
    print("   - MCP servers: chrome-devtools (browser automation)")
    print()

    return ClaudeSDKClient(
        options=ClaudeCodeOptions(
            model=model,
            system_prompt="You are an expert full-stack developer building a production-quality web application.",
            allowed_tools=[
                *BUILTIN_TOOLS,
                *BROWSER_TOOLS,
            ],
            mcp_servers={
                "chrome-devtools": {
                    "command": "npx",
                    "args": ["chrome-devtools-mcp@latest"],
                },
            },
            hooks={
                "PreToolUse": [
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                ],
            },
            max_turns=1000,
            cwd=str(project_dir.resolve()),
            settings=str(settings_file.resolve()),  # Use absolute path
        )
    )
