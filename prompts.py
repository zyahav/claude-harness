"""
Prompt Loading Utilities
========================

Functions for loading prompt templates from the prompts directory.
"""

import shutil
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text()


def get_initializer_prompt() -> str:
    """Load the initializer prompt."""
    return load_prompt("initializer_prompt")


def get_coding_prompt() -> str:
    """Load the coding agent prompt."""
    return load_prompt("coding_prompt")


def copy_spec_to_project(project_dir: Path, spec_path: Path = None) -> None:
    """Copy the app spec file into the project directory for the agent to read.
    
    Args:
        project_dir: Target project directory
        spec_path: Path to the spec file. If None, uses default app_spec.txt
    """
    if spec_path is None:
        spec_source = PROMPTS_DIR / "app_spec.txt"
    else:
        spec_source = spec_path
    
    if not spec_source.exists():
        raise FileNotFoundError(f"Spec file not found: {spec_source}")
    
    spec_dest = project_dir / "app_spec.txt"
    if not spec_dest.exists():
        shutil.copy(spec_source, spec_dest)
        print(f"Copied {spec_source.name} to project directory")
