"""Model router for the critique and refine tool."""
import logging
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core import exceptions as google_exceptions
from ..utils.config import (
    get_gemini_api_key,
    get_config,
    build_run_config,
    get_model_config,
)


# --- Custom Exception ---
class ModelAPIError(Exception):
    """Custom exception for model API-related errors."""


class ModelCallError(Exception):
    """Custom exception for errors during model calls."""


# --- Initialization ---
_is_initialized = False


def initialize(api_key: str):
    """Initializes the Google Generative AI client."""
    global _is_initialized
    if not api_key:
        raise ModelAPIError("Google Gemini API key is required for initialization.")
    try:
        genai.configure(api_key=api_key)
        _is_initialized = True
        logging.info("Google Generative AI client initialized successfully.")
    except Exception as e:
        raise ModelAPIError(f"Failed to configure Google Generative AI client: {e}") from e


def list_available_models() -> List[str]:
    """Lists available Gemini models from the API."""
    if not _is_initialized:
        raise ModelAPIError("Model router has not been initialized. Call initialize() first.")
    try:
        return [m.name for m in genai.list_models()]
    except Exception as e:
        logging.error("Could not list available models from the API: %s", e)
        return []


def _create_generation_config(
    config: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Create GenerationConfig and SafetySettings from a config dictionary.

    Args:
        config: A dictionary containing model configuration parameters.

    Returns:
        A dictionary with 'generation_config' and 'safety_settings' objects.
    """
    # Default to an empty dictionary if config is None
    config = config or {}

    # Generation Config
    gen_config_params = {
        key: config[key]
        for key in ["temperature", "max_output_tokens", "top_k", "top_p"]
        if key in config
    }
    generation_config_obj = genai.GenerationConfig(**gen_config_params) if gen_config_params else None

    # Safety Settings
    safety_settings_list = []
    if "safety_settings" in config and isinstance(config["safety_settings"], list):
        for setting in config["safety_settings"]:
            if isinstance(setting, dict) and "category" in setting and "threshold" in setting:
                try:
                    category_enum = HarmCategory[setting["category"]]
                    threshold_enum = HarmBlockThreshold[setting["threshold"]]
                    safety_settings_list.append(
                        {"category": category_enum, "threshold": threshold_enum}
                    )
                except (KeyError, AttributeError) as e:
                    logging.warning(
                        "Invalid safety setting '%s': %s. Skipping.", setting, e
                    )

    return {
        "generation_config": generation_config_obj,
        "safety_settings": safety_settings_list if safety_settings_list else None,
    }


async def call_gemini(
    prompt: str,
    model_name: str,
    system_prompt: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
) -> str:
    """Call the Gemini model using the Google Generative AI SDK.

    Args:
        prompt: The user prompt to send to the model.
        model_name: The name of the model to use.
        system_prompt: An optional system-level instruction.
        config: A dictionary containing generation and safety settings.

    Returns:
        The model's generated text response.

    Raises:
        ModelAPIError: If the API call fails or the router is not initialized.
    """
    if not _is_initialized:
        raise ModelAPIError("Model router has not been initialized. Call initialize() first.")
        
    try:
        model_kwargs = _create_generation_config(config)
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        response = await model.generate_content_async(
            contents=[{"text": prompt}],
            generation_config=model_kwargs["generation_config"],
            safety_settings=model_kwargs["safety_settings"],
        )
        return response.text
    except (
        google_exceptions.GoogleAPICallError,
        google_exceptions.RetryError,
        genai.types.generation_types.StopCandidateException,
    ) as e:
        logging.error("Error calling Gemini model %s: %s", model_name, e)
        raise ModelAPIError(f"Gemini API call failed for {model_name}") from e
    except Exception as e:
        logging.error("An unexpected error occurred while calling Gemini model %s: %s", model_name, e)
        raise ModelAPIError(f"An unexpected error occurred with model {model_name}") from e


async def call_model(
    prompt: str,
    model_name: Optional[str] = None,
    system_prompt: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    role: Optional[str] = None,
) -> str:
    """Abstract an LLM API call, handling routing, configuration, and fallbacks.

    This function determines the correct model to use based on the provided
    role or defaults, merges configurations, and handles API errors by
    attempting to use a fallback model if one is configured.

    Args:
        prompt: The user prompt.
        model_name: The specific model to use (overrides role-based selection).
        system_prompt: A system-level instruction for the model.
        config: A dictionary of configuration overrides.
        dry_run: If True, skips the actual API call and returns a mock response.
        role: The role of the agent (e.g., 'generator', 'critic') to determine
              which model to use.

    Returns:
        The model's response as a string.

    Raises:
        ValueError: If no model can be determined.
        ModelAPIError: If the primary and any fallback model calls fail.
    """
    # 1. Get configurations
    main_config = get_config()
    _model_config = main_config.get("models", {})
    _roles_config = main_config.get("roles", {})
    default_generation_config = main_config.get("generation", {})
    effective_config = {
        **default_generation_config,
        **_model_config,
        **(config or {}),
    }

    # 2. Determine model to use
    model_to_use = model_name
    if not model_to_use:
        # Strip .txt from role if it exists
        role_name = role.replace(".txt", "") if role else ""
        if role_name and role_name in _roles_config:
            model_to_use = _roles_config[role_name].get("model")
        else:
            model_to_use = effective_config.get("default_model")

    if not model_to_use:
        raise ValueError("No model name provided or configured.")

    logging.debug("Effective model config: %s", effective_config)

    # 3. Handle Dry Run
    if dry_run:
        logging.info("Dry run: Skipping actual model call to %s.", model_to_use)
        return f"DRY_RUN_RESPONSE: This is a mocked response for model {model_to_use}."

    # 4. Handle Mock Models for testing
    if model_to_use.startswith("mock"):
        return f"MOCK_RESPONSE: This is a mocked response for model {model_to_use}."

    # 5. Primary Model Call
    try:
        return await call_gemini(prompt, model_to_use, system_prompt, effective_config)
    except ModelAPIError as e:
        logging.warning(
            "Model call to %s failed with error: %s. Attempting fallback.",
            model_to_use,
            e,
        )

        # 6. Fallback Logic
        fallback_model = effective_config.get("fallback_model")
        if not fallback_model or model_to_use == fallback_model:
            raise ModelAPIError(f"Model {model_to_use} failed and no distinct fallback is available.") from e

        logging.info("Falling back to model: %s", fallback_model)
        try:
            return await call_gemini(prompt, fallback_model, system_prompt, effective_config)
        except ModelAPIError as fallback_e:
            raise ModelAPIError(f"Fallback model {fallback_model} also failed.") from fallback_e
