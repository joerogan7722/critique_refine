"""Configuration management for the critique and refine tool."""
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime
import logging

import yaml

from ..core.roles import load_role_template, TemplateNotFoundError
from ..core.config import RunConfig


try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # This warning is fine, as it indicates an optional dependency is missing.
    # For a personal tool, this is acceptable.
    pass


_config: Optional[Dict[str, Any]] = None
_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config(config_path: Path = _CONFIG_PATH) -> None:
    """Load configuration from a JSON file into a module-level variable.

    This function fails fast if the file is not found or is malformed.

    Args:
        config_path: The path to the configuration file.
    """
    # pylint: disable=global-statement
    global _config
    try:
        logging.info("Loading configuration from: %s", config_path)
        with open(config_path, "r", encoding="utf-8") as f:
            _config = json.load(f)
    except FileNotFoundError as e:
        print(f"Error: Config file not found at {config_path}.")
        print("Please ensure 'config.json' exists in the project root.")
        raise SystemExit(1) from e
    except json.JSONDecodeError as e:
        print(f"Error: Could not decode config file at {config_path}.")
        print("Please ensure 'config.json' is valid JSON.")
        raise SystemExit(1) from e


def get_config() -> Dict[str, Any]:
    """Retrieve the entire loaded configuration.

    If the configuration is not already loaded, this function will trigger
    loading from the default path.

    Returns:
        The full configuration dictionary.
    """
    if _config is None:
        load_config()  # Load config if not already loaded
    assert _config is not None, "Config should be loaded by this point"
    return _config


def get(key: str, default: Any = None) -> Any:
    """Retrieve a configuration value by key."""
    return get_config().get(key, default)


def get_critique_refine_config() -> Dict[str, Any]:
    """Retrieve the critique_refine_config section."""
    return get("critique_refine_config", {})


def get_logging_config() -> Dict[str, Any]:
    """Retrieve the logging_config section."""
    return get("logging_config", {})


_strategies_config: Optional[Dict[str, Any]] = None
_STRATEGIES_PATH = Path(__file__).parent.parent / "strategies.yaml"


def load_strategies_config(strategies_path: Path = _STRATEGIES_PATH) -> None:
    """Load strategies from a YAML file."""
    # pylint: disable=global-statement
    global _strategies_config
    if not strategies_path.exists():
        _strategies_config = {}
        return
    try:
        with open(strategies_path, "r", encoding="utf-8") as f:
            _strategies_config = yaml.safe_load(f)
    except (yaml.YAMLError, IOError) as e:
        print(f"Warning: Could not load or parse strategies.yaml: {e}")
        _strategies_config = {}


def get_strategies_config_all() -> Dict[str, Any]:
    """Retrieve the loaded strategies configuration."""
    if _strategies_config is None:
        load_strategies_config()
    assert _strategies_config is not None
    return _strategies_config.get("strategies", {})


def get_strategy_config(strategy_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve configuration for a specific strategy."""
    return get_strategies_config_all().get(strategy_name)


def get_project_context_path() -> Optional[Path]:
    """Retrieve the project context path from the configuration."""
    path_str = get("project_context_path")
    return Path(path_str) if path_str else None


def get_model_config() -> Dict[str, Any]:
    """Retrieve the model configuration section."""
    return get("models", {})


def get_roles_config() -> Dict[str, Any]:
    """Retrieve the roles configuration section."""
    return get("roles", {})


def get_default_generation_config() -> Dict[str, Any]:
    """Retrieve default generation config parameters."""
    return get_model_config().get("default_generation_config", {})


def get_redaction_config() -> Dict[str, Any]:
    """Retrieve the redaction configuration section."""
    return get("redaction_config", {})


def get_supported_models() -> Dict[str, Any]:
    """Retrieve the supported models configuration."""
    return get_model_config().get("supported", {})


def get_gemini_api_key() -> Optional[str]:
    """Retrieve the Google Gemini API Key from environment variables."""
    return os.getenv("GEMINI_API_KEY")


def prepare_run_environment(run_args: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare the run configuration by merging base config, strategies, and CLI overrides.

    Args:
        run_args: A dictionary of run arguments.

    Returns:
        A dictionary containing the merged configuration and loaded roles.

    Raises:
        ValueError: If a specified strategy or role template is not found.
    """
    current_config = get_critique_refine_config().copy()
    
    # Set default roles from the critique_refine_config
    critique_refine_config = get_critique_refine_config()
    current_config["default_critic_role_prompt_file"] = critique_refine_config.get("default_critic_role")
    current_config["default_refiner_role_prompt_file"] = critique_refine_config.get("default_refiner_role")

    strategy = run_args.get("strategy")
    if strategy:
        import logging
        logging.info("Applying strategy: %s", strategy)
        strategy_config = get_strategy_config(strategy)
        if not strategy_config:
            raise ValueError(f"Strategy '{strategy}' not found in strategies.yaml.")

        if isinstance(strategy_config, list):
            # Strategy is a simple list of roles (e.g., final_cleanup_deep)
            current_config["multi_critic_roles"] = [
                f"{role}.txt" for role in strategy_config
            ]
            current_config.pop("default_critic_role_prompt_file", None)
        elif isinstance(strategy_config, dict):
            # Strategy is a dictionary with configuration
            if "roles" in strategy_config and isinstance(strategy_config["roles"], list):
                current_config["multi_critic_roles"] = [
                    f"{role}.txt" for role in strategy_config["roles"]
                ]
                current_config.pop("default_critic_role_prompt_file", None)
            
            # Handle specific refiner role if defined in strategy
            if "default_refiner_role_prompt_file" in strategy_config:
                current_config["default_refiner_role_prompt_file"] = strategy_config["default_refiner_role_prompt_file"]

            # Update other config items from strategy (e.g., max_rounds, stop_threshold, models)
            current_config.update(strategy_config)
            # Remove roles key from current_config to avoid conflicts with multi_critic_roles
            current_config.pop("roles", None)

    critic_role = run_args.get("critic_role")
    if critic_role:
        import logging
        logging.info("Overriding critic role with CLI argument: %s", critic_role)
        current_config["default_critic_role_prompt_file"] = critic_role
        if "multi_critic_roles" in current_config:
            logging.warning(
                "CLI argument --critic-role overrides multi-critic strategy."
            )
            del current_config["multi_critic_roles"]

    refiner_role = run_args.get("refiner_role")
    if refiner_role:
        import logging
        logging.info("Overriding refiner role with CLI argument: %s", refiner_role)
        current_config["default_refiner_role_prompt_file"] = refiner_role

    multi_critic_roles = run_args.get("multi_critic_roles")
    if multi_critic_roles:
        current_config["multi_critic_roles"] = multi_critic_roles.split(",")
        if "default_critic_role_prompt_file" in current_config:
            del current_config["default_critic_role_prompt_file"]

    # Load roles
    roles = {}
    # Load roles from config, with fallbacks for safety
    critique_refine_config = get_critique_refine_config()
    critic_role_file = current_config.get("default_critic_role_prompt_file") or critique_refine_config.get("default_critic_role", "critic.txt")
    refiner_role_file = current_config.get("default_refiner_role_prompt_file") or critique_refine_config.get("default_refiner_role", "refiner.txt")

    try:
        roles["critic_template"] = load_role_template(critic_role_file)
        roles["refiner_template"] = load_role_template(refiner_role_file)
        
        # Also load meta-critic for the loop, if defined
        meta_critic_role = critique_refine_config.get("meta_critic_role")
        if meta_critic_role:
            roles["meta_critic_template"] = load_role_template(meta_critic_role)
            
    except (TemplateNotFoundError, IOError) as e:
        raise ValueError(f"Error loading role template: {e}") from e

    return {"config": current_config, "roles": roles}


def build_run_config(run_args: Dict[str, Any], full_config: Dict[str, Any]) -> RunConfig:
    """Build a RunConfig object from command-line arguments and the full application config.

    Args:
        run_args: A dictionary of run arguments.
        full_config: The full application configuration.

    Returns:
        A populated RunConfig object.
    """
    run_env = prepare_run_environment(run_args)
    current_config = run_env["config"]
    roles = run_env["roles"]

    logging_config = get_logging_config()
    log_dir = Path(logging_config.get("log_dir", "logs"))
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_name = f"run_{timestamp}.jsonl"
    log_file_path = str(log_dir / log_file_name)

    return RunConfig(
        generator_model=current_config.get("generator_model", "gemini-1.5-flash"),
        critic_model=current_config.get("critic_model", "gemini-1.5-flash"),
        refiner_model=current_config.get("refiner_model", "gemini-1.5-flash"),
        meta_critic_model=current_config.get("meta_critic_model", "gemini-1.5-flash"),
        fallback_model=current_config.get("fallback_model", "gemini-1.5-flash"),
        max_rounds=current_config.get("max_rounds", 3),
        stop_threshold=current_config.get("stop_on_no_actionable_critique_threshold", 50),
        log_file_path=log_file_path,
        redact_logs=run_args.get("redact_logs") or logging_config.get("redact_sensitive_data", False),
        full_config=full_config,
        roles=roles,
        default_critic_role_prompt_file=current_config.get("default_critic_role_prompt_file"),
        default_refiner_role_prompt_file=current_config.get("default_refiner_role_prompt_file"),
        multi_critic_roles=current_config.get("multi_critic_roles"),
        disable_meta_critic=current_config.get("disable_meta_critic", False),
        dry_run=bool(run_args.get("dry_run")),  # Ensure dry_run is a boolean
    )
