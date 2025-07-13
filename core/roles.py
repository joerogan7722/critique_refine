from pathlib import Path
from typing import Optional
import functools


class TemplateNotFoundError(Exception):
    """Custom exception for when a template file is not found."""


def load_role_template(file_name: str, base_dir: Optional[Path] = None) -> str:
    """
    Loads a role template from the 'prompts' directory.

    Args:
        file_name: The name of the role template file (e.g., "critic.txt").
        base_dir: Optional. The base directory to search for the 'prompts' folder.
                  If None, it defaults to the 'prompts' directory relative to this file.

    Returns:
        The content of the role template file.

    Raises:
        TemplateNotFoundError: If the template file does not exist.
        IOError: If there's another error reading the file.
    """
    if base_dir is None:
        # The 'prompts' directory is relative to this file's location (core/roles.py)
        # So we go up one level to the 'critique_refine' directory, then into 'prompts'.
        base_dir = Path(__file__).parent.parent / "prompts"

    file_path = base_dir / file_name
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError as e:
        raise TemplateNotFoundError(f"Prompt template not found at {file_path}") from e
    except OSError as e:
        raise IOError(f"Error loading prompt template from {file_path}: {e}") from e


# Apply LRU cache to the function
load_role_template = functools.lru_cache(maxsize=None)(load_role_template)