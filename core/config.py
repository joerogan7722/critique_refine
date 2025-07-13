from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RunConfig:
    """
    Configuration for a single critique and refine loop run.
    """
    generator_model: str
    critic_model: str
    refiner_model: str
    meta_critic_model: str
    fallback_model: str
    max_rounds: int
    stop_threshold: int
    log_file_path: str
    redact_logs: bool
    full_config: Dict[str, Any]
    roles: Dict[str, str]
    default_critic_role_prompt_file: Optional[str] = None
    default_refiner_role_prompt_file: Optional[str] = None
    multi_critic_roles: Optional[List[str]] = None
    disable_meta_critic: bool = False
    dry_run: bool = False
