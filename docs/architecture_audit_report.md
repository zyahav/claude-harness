# Independent Architecture Audit: Harness-Lab

**Date:** December 23, 2025  
**Auditor:** Antigravity (Google Deepmind)  
**Subject:** Transition to Multi-Provider "Universal Intelligence Console"

## 1. Executive Summary

The internal audit findings are **Confirmed**. The current `harness-lab` codebase is tightly coupled to the `claude-code-sdk`, specifically in `agent.py` and `client.py`. The system relies on Anthropic-specific message types (`AssistantMessage`, `ToolUseBlock`) and implicit tool definitions (`Read(./**)` strings).

Transitioning to a Multi-Provider system (Z.ai, Hugging Face, OpenRouter) is feasible but requires a significant refactor to decouple the "Intelligence Loop" from the "Provider SDK".

## 2. Architecture Critique: The Provider Factory

**Is the "Provider Factory" the right approach?**
**Verdict:** ✅ **YES, Critical Path.**

The current implementation in `client.py` lazy-loads `claude_code_sdk` inside `create_client`. This is a rudimentary factory but hardcodes the return type to `ClaudeSDKClient`.

**Recommendation:**
Refactor `create_client` into a true **Provider Factory Pattern**.
- Define an abstract base class `AgentProvider`.
- `AgentProvider` must expose standard methods: `send_message(history)`, `stream_response()`, and `get_tool_definitions()`.
- Create concrete implementations: `AnthropicProvider`, `OpenAIProvider` (covers Z.ai/GLM), `HuggingFaceProvider`.
- The main loop in `agent.py` should act on `AgentProvider`, not `ClaudeSDKClient`.

## 3. Protocol Strategy: Unified Message Format

**The Challenge:** Anthropic uses `content` blocks (Text, ToolUse). OpenAI uses `tool_calls` array. Hugging Face uses various chat templates.

**Strategy: "The Canonical Message Protocol"**
Do not try to make every provider speak Anthropic's dialect. Instead, introduce an internal **Canonical Schema** (`schema.py` expansion) that represents:
- `SystemMessage`
- `UserMessage` (Text + Images)
- `AssistantMessage` (Text + ToolCalls)
- `ToolResultMessage` (Result + Error)

**Implementation:**
- **Inbound:** The Provider Adaptor converts the model-specific response (e.g., OpenAI JSON) into the Canonical Message.
- **Outbound:** The Provider Adaptor converts the Canonical History into the format expected by the model API (e.g., `messages=[{"role": "user", ...}]`).

## 4. Tool Translation: The "Read/Bash" Facelift

**Problem:** `BUILTIN_TOOLS` like `Edit` and `Bash` are currently provided by the `claude-code-sdk` black box. Moving to Z.ai means losing these implementations.

**Safest Strategy: "MCP Correctness"**
The safest way to map these tools is to **externalize them entirely via MCP**.
1. **Do not rewrite** `Read`/`Write`/`Edit` inside the generic agent.
2. **Use/Build a "FileSystem MCP Server"**: This server should expose `read_file`, `write_file`, and `edit_file` (patching) tools.
3. **Connect All Agents to this MCP**:
   - For Anthropic: The MCP server translates to the creation of client-side tools (existing behavior).
   - For Z.ai/OpenRouter: The MCP server provides the JSON Schema for tool definitions and handles the execution.

**Benefit:** This treats the "File System" as just another external resource, making the Agent Provider agnostic.

## 5. Context Handoff Strategy

**Scenario:** Researcher (Llama) -> Coder (GLM).

**Strategy: "The Context Envelope"**
`handoff.json` is currently just a task list. It needs to become a snapshot of the *Intelligence State*.

**Proposed Structure:**
```json
{
  "meta": { "last_provider": "llama-3.1", "timestamp": "..." },
  "memory_bank": {
    "summary": "Agent analyzed repo and found 3 bugs in auth flow.",
    "key_decisions": ["Use JWT", "Refactor login.py"],
    "active_context_files": ["src/login.py", "src/auth.ts"]
  },
  "tasks": [ ... ] 
}
```

**Workflow:**
1. **serialization**: When Agent A finishes, it generates a "Handoff Summary" (using an LLM call if needed) and saves it to the `memory_bank`.
2. **deserialization**: Agent B starts, reads the `memory_bank`, and loads the `active_context_files` into its immediate context window as a `System` or `User` prompt.
3. **Amnesia**: Do **not** pass the full raw message history between different providers. Tokenizers vary, and formats break. Pass only the *Resulting State* (Files + Memory Bank).

## 6. Implementation Pitfalls (Top 3 Risks)

1. **Loss of High-Fidelity Tools (The "Edit" Problem)**
   - **Risk:** The `claude-code-sdk` "Edit" tool is highly optimized for code patching. Generic replacements (e.g., standard explicit write) are often dumber and lead to file corruption.
   - **Mitigation:** You must implement a robust "Smart Edit" MCP tool that handles diffs/patching, or coding performance will degrade significantly on non-Anthropic models.

2. **Prompt Fragility**
   - **Risk:** Prompts in `prompts.py` are likely tuned for Claude (XML tags, specific phrasing). GLM-4 or Llama might hallucinate or ignore instructions with these prompts.
   - **Mitigation:** Isolate prompts. `ProviderFactory` should load `prompts/anthropic/` vs `prompts/openai/`. Do not share prompts initially.

3. **Tool Calling Divergence**
   - **Risk:** Some models (like older Llama) struggle with "multi-tool usage" or formatted arguments. If the core loop expects perfect JSON tool calls, it will crash.
   - **Mitigation:** Implement a "Robust Parser" in the Provider Adapter that can handle malformed JSON or "Markdown-wrapped" tool calls, which often happen with weaker open-weight models.
