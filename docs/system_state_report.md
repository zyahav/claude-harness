# System State Report & Architecture Audit
**Date:** 2025-12-22
**Status:** Audit Complete
**Target:** Harness-Lab Multi-Provider Transition

## 1. Executive Summary

The current `harness-lab` codebase is a compact, focused implementation heavily optimized for the `claude-code-sdk`. It uses Git worktrees for isolation (`lifecycle.py`) and tracks progress via a `handoff.json` file.

**Feasibility Verdict:** **GO**.
The transition to a multi-provider system is feasible but will require a **significant refactor of the `client.py` and `agent.py` modules**, which are currently inextricably linked to the Anthropic SDK. The rest of the system (`harness.py`, `lifecycle.py`, `schema.py`) provides a solid foundation that can be preserved.

---

## 2. Technical Audit: System State Report

### A. Core Agent Logic & Memory

| Feature | Current Implementation | Analysis for Migration |
| :--- | :--- | :--- |
| **Memory Persistence** | File-based via `handoff.json` in the project worktree. Status is boolean (`passes: true/false`). | **Reusable.** This is state-agnostic and can be extended to track which provider completed which task. |
| **Context Window** | Implicitly managed by `claude-code-sdk`. `client.py` sets `max_turns=1000`. | **Refactor Required.** We need a unified `ContextManager` to handle history truncation strategies for models with different context limits (e.g. Llama-3.1 vs Claude). |
| **Loop Independence** | **High Coupling.** `agent.py` iterates over `ClaudeSDKClient` message types (`AssistantMessage`, `ToolUseBlock`). | **Breaking Change.** The Plan-Act-Review loop will break immediately if the client is swapped. An abstraction layer (`AgentAdapter`) is needed to normalize responses from Z.ai/OpenAI formats into a common internal object model. |

### B. Protocol & Tooling

*   **Tool Schema:** Defined implicitly by passing string names (`"Read"`, `"Bash"`) to `ClaudeCodeOptions` in `client.py`. There is no explicit JSON schema definition in the repo; the SDK handles it.
*   **Parsing Logic:** The code relies on the SDK's object model (`block.text`, `block.input`). It does **not** use raw XML parsing in the user-code to extract "Thinking" blocks or tool calls.
*   **Streaming:** `agent.py` uses `async for msg in client.receive_response()`. This is an SDK-specific async iterator.

### C. The `spec.json` Structure

**Current State (`schema.py`):**
The system uses a `Task` dataclass (persisted as `handoff.json`) with the following structure:
```json
{
  "id": "TASK-001",
  "category": "api",
  "title": "Task Title",
  "description": "Task Description",
  "passes": false
}
```

**Target State Gap:**
To support the vision, the `Task` schema must be updated to support execution overrides:
```json
{
  "id": "TASK-001",
  "title": "Task Title",
  "overrides": {
      "provider": "zai",
      "model": "glm-4.7"
  }
}
```

---

## 3. Immediate Requirements for Dev Team

### Dependency Map
*   **Core:** `claude-code-sdk>=0.0.25`
*   **Env:** `python-dotenv`
*   **Stdlib:** `asyncio`, `json`, `pathlib`, `subprocess`

### Modular Audit
*   **LLM Client:** Centralized in `client.py` -> `create_client(project_dir, model)`. This function returns a `ClaudeSDKClient` directly.
*   **Agent Loop:** `agent.py` -> `run_agent_session` consumes the client.

### Credential Management
*   **Current:** `client.py` reads `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_API_KEY` from `os.environ`.
*   **Missing:** No logic exists for `ZAI_API_KEY`, `HF_TOKEN`, or `OPENROUTER_API_KEY`.

---

## 4. Implementation Roadmap (Recommended)

To achieve the "Universal Intelligence Console" without breaking existing functionality, we recommend the following 3-phase plan:

### Phase 1: The Abstraction Layer ("Provider Factory")
Create a protocol `LLMProvider` that mirrors the functionality used in `agent.py`:
- `query(message: str)`
- `receive_response() -> Iterator[UnifiedMessage]`
- Implement `AnthropicProvider` (wrapping current SDK) and `OpenAIProvider` (for Z.ai/GLM).

### Phase 2: Schema Evolution
Update `schema.py` to include `provider` and `model` fields in the `Task` dataclass.

### Phase 3: The Orchestrator
Modify `harness.py` to read the new spec, instantiate the correct provider from the factory for each task, and pass it to a genericized `run_agent_session`.

---

## 5. Decision for Leadership

**Opinion:** The "Strategic Handoff" is **VALID** and effectively planned.
Do not "leave the code as is." The current codebase is too specific to effectively serve as a multi-provider harness without the proposed changes. However, the *structure* (worktrees + independent task tracking) is excellent and should be kept.

**Recommendation:** Proceed with creating the `Provider Factory` described in Section 5.
