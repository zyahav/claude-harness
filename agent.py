"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions.
"""

import asyncio
from pathlib import Path
from typing import Optional

# from claude_code_sdk import ClaudeSDKClient

from client import create_client
from progress import print_session_header, print_progress_summary
from prompts import get_initializer_prompt, get_prompt_for_mode, copy_spec_to_project
import schema

import logging

logger = logging.getLogger(__name__)

# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


async def run_agent_session(
    client: "ClaudeSDKClient",
    message: str,
    project_dir: Path,
) -> tuple[str, str]:
    """
    Run a single agent session using Claude Agent SDK.

    Args:
        client: Claude SDK client
        message: The prompt to send
        project_dir: Project directory path

    Returns:
        (status, response_text) where status is:
        - "continue" if agent should continue working
        - "error" if an error occurred
    """
    logger.info("Sending prompt to Claude Agent SDK...\n")

    try:
        # Send the query
        await client.query(message)

        # Collect response text and show tool use
        response_text = ""
        async for msg in client.receive_response():
            msg_type = type(msg).__name__

            # Handle AssistantMessage (text and tool use)
            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        response_text += block.text
                        logger.info(block.text) # Using info for main text
                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        logger.info(f"\n[Tool: {block.name}]")
                        if hasattr(block, "input"):
                            input_str = str(block.input)
                            if len(input_str) > 200:
                                logger.info(f"   Input: {input_str[:200]}...")
                            else:
                                logger.info(f"   Input: {input_str}")

            # Handle UserMessage (tool results)
            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "ToolResultBlock":
                        result_content = getattr(block, "content", "")
                        is_error = getattr(block, "is_error", False)

                        # Check if command was blocked by security hook
                        if "blocked" in str(result_content).lower():
                            logger.warning(f"   [BLOCKED] {result_content}")
                        elif is_error:
                            # Show errors (truncated)
                            error_str = str(result_content)[:500]
                            logger.error(f"   [Error] {error_str}")
                        else:
                            # Tool succeeded - just show brief confirmation
                            logger.info("   [Done]")

        logger.info("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        logger.error(f"Error during agent session: {e}", exc_info=True)
        return "error", str(e)


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
    spec_path: Optional[Path] = None,
    mode: str = "greenfield",
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        max_iterations: Maximum number of iterations (None for unlimited)
        spec_path: Path to the constitution/spec file (None for default)
        mode: 'greenfield' (new project) or 'brownfield' (existing codebase)
    """
    mode_label = "GREENFIELD" if mode == "greenfield" else "BROWNFIELD"
    logger.info("\n" + "=" * 70)
    logger.info(f"  AUTONOMOUS CODING AGENT ({mode_label})")
    logger.info("=" * 70)
    logger.info(f"\nProject directory: {project_dir}")
    logger.info(f"Model: {model}")
    logger.info(f"Mode: {mode}")
    if max_iterations:
        logger.info(f"Max iterations: {max_iterations}")
    else:
        logger.info("Max iterations: Unlimited (will run until completion)")
    logger.info("")

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a fresh start or continuation
    tests_file = project_dir / "handoff.json"
    is_first_run = not tests_file.exists()

    if is_first_run:
        logger.info("Fresh start - will use initializer agent")
        logger.info("")
        logger.info("=" * 70)
        logger.info("  NOTE: First session takes 10-20+ minutes!")
        logger.info("  The agent is generating 200 detailed test cases.")
        logger.info("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        logger.info("=" * 70)
        logger.info("")
        # Copy the app spec into the project directory for the agent to read
        copy_spec_to_project(project_dir, spec_path)
    else:
        logger.info("Continuing existing project")
        
        # Validate schema before continuing
        errors = schema.validate_handoff_file(tests_file)
        if errors:
            logger.error(f"\nError: handoff.json is invalid:")
            for error in errors:
                logger.error(f"  - {error}")
            logger.error("\nPlease fix the schema errors before continuing.")
            return

        print_progress_summary(project_dir)

    # Main loop
    iteration = 0

    # Main loop
    iteration = 0
    consecutive_errors = 0
    backoff_seconds = 1

    while True:
        iteration += 1

        # Check max iterations
        if max_iterations and iteration > max_iterations:
            logger.info(f"\nReached max iterations ({max_iterations})")
            logger.info("To continue, run the script again without --max-iterations")
            break

        # Print session header
        # TODO: Update progress.py to use logging or capture its output
        print_session_header(iteration, is_first_run)

        # Create client (fresh context)
        client = create_client(project_dir, model)

        # Choose prompt based on session type
        if is_first_run:
            prompt = get_initializer_prompt()
            is_first_run = False  # Only use initializer once
        else:
            prompt = get_prompt_for_mode(mode)

        # Run session with async context manager
        async with client:
            status, response = await run_agent_session(client, prompt, project_dir)

        # Handle status
        if status == "continue":
            # Success! Reset backoff
            consecutive_errors = 0
            backoff_seconds = 1
            
            logger.info(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            consecutive_errors += 1
            logger.error("\nSession encountered an error")
            
            if consecutive_errors > 5:
                logger.critical("Too many consecutive errors. Aborting.")
                break
                
            logger.warning(f"Retrying in {backoff_seconds}s... (Attempt {consecutive_errors}/5)")
            await asyncio.sleep(backoff_seconds)
            backoff_seconds *= 2  # Exponential backoff

        # Small delay between sessions if not error
        if status != "error" and (max_iterations is None or iteration < max_iterations):
            logger.info("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    # Print instructions for running the generated application
    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")
