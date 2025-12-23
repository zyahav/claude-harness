# Architecture Decision Record 001: Lazy Loading of Claude SDK

**Date:** 2025-12-22
**Status:** Proposed
**Author:** Gemini Agent

## Context
The `harness-lab` project is a CLI tool designed to orchestrate autonomous coding agents. Currently, the project has a hard, top-level dependency on the `claude_code_sdk` library in its core modules (`agent.py` and `client.py`).

## The Problem
When a user runs `harness.py`, Python attempts to import all dependencies immediately at the top of the file. If `claude_code_sdk` is not installed in the current environment, the program crashes with a `ModuleNotFoundError`.

This occurs even for operations that **do not** require the SDK, such as:
1.  Displaying the help menu (`python harness.py --help`).
2.  Validating project configuration files (e.g., `handoff.json` schema validation).
3.  Running setup or initialization scripts that prepare the environment before the agent runs.

This creates a brittle user experience where the tool is unusable for basic tasks unless the full runtime environment is perfectly set up.

## Proposed Solution
Refactor `agent.py` and `client.py` to use **Lazy Importing**.

Instead of importing the SDK at the top of the file:
```python
# Current (Bad)
from claude_code_sdk import ClaudeSDKClient

def create_client():
    ...
```

We will move the import inside the specific functions that actually use it:
```python
# Proposed (Good)
def create_client():
    from claude_code_sdk import ClaudeSDKClient  # Only imported when function is called
    ...
```

## Impact Analysis

### Benefits
1.  **Robustness:** The CLI becomes more resilient. Users can run `--help` or validation commands even if the SDK is missing.
2.  **Performance:** Startup time for simple commands is reduced as fewer libraries are loaded.
3.  **Testability:** We can write and run tests for the harness logic (like schema validation) in CI environments that might not have the full heavy SDK installed.

### Risks
*   **Type Hinting:** Python type hints often require the class to be imported. We will mitigate this by using string forward references (e.g., `client: "ClaudeSDKClient"`) which is a standard Python practice.
*   **Runtime Errors:** If the SDK is missing, the error will happen later (when the agent starts) rather than immediately. This is actually preferred behavior, as we can catch it and provide a helpful "Please install dependencies" message.

## Recommendation
Approve the refactoring of `agent.py` and `client.py` to implement lazy imports for `claude_code_sdk`. This is a low-risk, high-value change that significantly improves the tool's quality.
