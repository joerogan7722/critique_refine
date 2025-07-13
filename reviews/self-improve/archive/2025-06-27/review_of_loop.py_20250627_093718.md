# Self-Review of core\loop.py

**Timestamp:** 2025-06-27T09:37:18.313149

**Original Content:**
```
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
# Local imports
from core.model_router import call_model
from core.roles import load_role_template, TemplateNotFoundError
from utils.logger import Logger
from .config import RunConfig


class CritiqueRefineLoop:
    """
    Encapsulates the logic for the critique and refinement loop.
    """

    def __init__(self, run_config: RunConfig):
        """
        Initializes the loop with a specific run configuration.

        Args:
            run_config: The configuration for this loop instance.
        """
        self.run_config = run_config
        redaction_config = self.run_config.full_config.get("redaction_config", {})
        self.logger = Logger(
            log_file_path=self.run_config.log_file_path,
            redact=self.run_config.redact_logs,
            keys_to_redact=redaction_config.get("keys_to_redact"),
            redaction_patterns=redaction_config.get("patterns_to_redact"),
        )
        self.run_log: Dict[str, Any] = {}

    async def _generate(
        self, initial_user_prompt: str, initial_content_for_review: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Handle the initial content generation or loading phase.

        If initial content is provided, it's used directly. Otherwise, the generator
        model is called with the user's prompt.

        Args:
            initial_user_prompt: The user's starting prompt.
            initial_content_for_review: Existing content to be reviewed.

        Returns:
            A tuple containing the initial text and a log dictionary.
        """
        logging.info("Entering generation phase...")
        initial_generation_log = {}
        if initial_content_for_review:
            initial_response = initial_content_for_review
            initial_generation_log = {
                "text": initial_response,
                "model_used": "N/A (provided content for review)",
            }
            logging.info("\n--- Content for Review ---\n%s\n", initial_response)
        else:
            initial_response = await call_model(
                prompt=f"User prompt: {initial_user_prompt}",
                model_name=self.run_config.generator_model,
                config=self.run_config.full_config,
                dry_run=self.run_config.dry_run,
                role="generator",
            )
            initial_generation_log = {
                "text": initial_response,
                "model_used": self.run_config.generator_model,
            }
            logging.info("\n--- Initial Response ---\n%s\n", initial_response)
        return initial_response, initial_generation_log

    async def _critique(
        self, current_text: str, round_num: int
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate a critique for the given text.

        If multiple critic roles are configured, it runs them in parallel and
        combines their critiques. Otherwise, it uses a single critic.

        Args:
            current_text: The text to be critiqued.
            round_num: The current iteration number.

        Returns:
            A tuple containing the critique and a log dictionary.

        Raises:
            ValueError: If a required prompt template is not found.
        """
        logging.info("Entering critique phase (Round %d)...", round_num)
        critique_log = {}
        if self.run_config.multi_critic_roles:
            logging.info(
                "--- Multi-agent Critique (Roles: %s) ---",
                ", ".join(self.run_config.multi_critic_roles),
            )

            async def get_critique(role_file):
                role_template = load_role_template(role_file)
                return await call_model(
                    prompt=current_text,
                    model_name=self.run_config.critic_model,
                    system_prompt=role_template,
                    config=self.run_config.full_config,
                    dry_run=self.run_config.dry_run,
                    role="critic",
                )

            try:
                critiques = await asyncio.gather(
                    *[
                        get_critique(role_file)
                        for role_file in self.run_config.multi_critic_roles
                    ]
                )
            except (TemplateNotFoundError, IOError) as e:
                logging.error("Failed to load critic prompt template: %s", e)
                raise ValueError(
                    "Failed to load one or more critic prompt templates."
                ) from e
            critique = "\n\n".join(critiques)
            critique_log = {
                "round": round_num,
                "text": critique,
                "model_used": self.run_config.critic_model,
                "role_prompt_file_used": self.run_config.multi_critic_roles,
            }
        else:
            critique = await call_model(
                prompt=current_text,
                model_name=self.run_config.critic_model,
                system_prompt=self.run_config.roles.get("critic_template"),
                config=self.run_config.full_config,
                dry_run=self.run_config.dry_run,
                role="critic",
            )
            critique_log = {
                "round": round_num,
                "text": critique,
                "model_used": self.run_config.critic_model,
                "role_prompt_file_used": self.run_config.default_critic_role_prompt_file,
            }
        logging.info("\n--- Critique ---\n%s\n", critique)
        return critique, critique_log

    async def _refine(
        self, current_text: str, critique: str, round_num: int
    ) -> Tuple[str, Dict[str, Any]]:
        """Refine the text based on the provided critique.

        Args:
            current_text: The text to be refined.
            critique: The critique to apply.
            round_num: The current iteration number.

        Returns:
            A tuple containing the refined text and a log dictionary.
        """
        logging.info("Entering refinement phase (Round %d)...", round_num)
        refine_prompt_for_model = (
            f"Original text:\n{current_text}\n\n"
            f"Critique:\n{critique}\n\n"
            "Refine the original text based on the critique."
        )
        refined_response = await call_model(
            prompt=refine_prompt_for_model,
            model_name=self.run_config.refiner_model,
            system_prompt=self.run_config.roles.get("refiner_template"),
            config=self.run_config.full_config,
            dry_run=self.run_config.dry_run,
            role="refiner",
        )
        refinement_log = {
            "round": round_num,
            "text": refined_response,
            "model_used": self.run_config.refiner_model,
            "role_prompt_file_used": self.run_config.default_refiner_role_prompt_file,
        }
        logging.info("\n--- Refined Response ---\n%s\n", refined_response)
        return refined_response, refinement_log

    async def run(
        self,
        initial_user_prompt: str,
        initial_content_for_review: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Runs the critique and refine loop.

        Args:
            initial_user_prompt: The initial prompt from the user.
            initial_content_for_review: Optional initial content for self-review mode.

        Returns:
            A tuple containing the final refined output (str) and the run log (dict).
        """
        self.run_log = {
            "timestamp": datetime.now().isoformat(),
            "original_user_prompt": initial_user_prompt,
            "context_documents": [],  # Placeholder for future RAG
            "initial_generation": {},
            "critiques": [],
            "refinements": [],
            "reason_for_stopping": "",
            "final_output": "",
            "config_used": {
                "generator_model": self.run_config.generator_model,
                "critic_model": self.run_config.critic_model,
                "refiner_model": self.run_config.refiner_model,
                "max_rounds": self.run_config.max_rounds,
                "stop_on_no_actionable_critique_threshold": self.run_config.stop_threshold,
                "default_critic_role_prompt_file": self.run_config.default_critic_role_prompt_file,
                "default_refiner_role_prompt_file": self.run_config.default_refiner_role_prompt_file,
                "multi_critic_roles": self.run_config.multi_critic_roles,
            },
        }

        try:
            current_text, initial_generation_log = await self._generate(
                initial_user_prompt, initial_content_for_review
            )
            self.run_log["initial_generation"] = initial_generation_log

            for i in range(self.run_config.max_rounds):
                critique_text, critique_log = await self._critique(current_text, i + 1)
                self.run_log["critiques"].append(critique_log)

                meta_critic_template = self.run_config.roles.get("meta_critic_template")
                if not meta_critic_template:
                    logging.warning("Meta-critic template not found in config, skipping actionability check.")
                else:
                    actionability_response = await call_model(
                        prompt=critique_text,
                        model_name=self.run_config.critic_model,  # Use a fast model for classification
                        system_prompt=meta_critic_template,
                        config=self.run_config.full_config,
                        dry_run=self.run_config.dry_run,
                        role="meta_critic",
                    )

                    if not actionability_response or not actionability_response.strip():
                        logging.warning("Meta-critic returned an empty or unexpected response.")
                    
                    if actionability_response.strip() == "NON_ACTIONABLE":
                        self.run_log["reason_for_stopping"] = (
                            f"Non-actionable critique received in round {i + 1}."
                        )
                        self.run_log["final_output"] = current_text
                        break

                refined_response, refinement_log = await self._refine(
                    current_text, critique_text, i + 1
                )
                self.run_log["refinements"].append(refinement_log)
                current_text = refined_response

            if not self.run_log["reason_for_stopping"]:
                self.run_log["reason_for_stopping"] = (
                    f"Max rounds ({self.run_config.max_rounds}) reached."
                )
            self.run_log["final_output"] = current_text

        except Exception as e:
            error_message = f"Error during critique/refine loop: {e}"
            logging.error(error_message, exc_info=True)
            self.run_log["reason_for_stopping"] = error_message
            self.run_log["final_output"] = ""
            raise
        finally:
            self.logger.log_run(self.run_log)

        return self.run_log["final_output"], self.run_log

```

**Critique-Refine Output:**
```python
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
import time

# Local imports
from core.model_router import call_model, ModelCallError
from core.roles import load_role_template, TemplateNotFoundError
from utils.logger import Logger
from .config import RunConfig


class CritiqueRefineLoop:
    """Encapsulates the critique and refinement loop logic."""

    def __init__(self, run_config: RunConfig):
        """Initializes the loop with a run configuration.

        Args:
            run_config: The configuration for this loop instance.
        """
        self.run_config = run_config
        redaction_config = self.run_config.full_config.get("redaction_config", {})
        self.logger = Logger(
            log_file_path=self.run_config.log_file_path,
            redact=self.run_config.redact_logs,
            keys_to_redact=redaction_config.get("keys_to_redact"),
            redaction_patterns=redaction_config.get("patterns_to_redact"),
        )
        self.generator_model = self.run_config.generator_model
        self.critic_model = self.run_config.critic_model
        self.refiner_model = self.run_config.refiner_model
        self.max_rounds = self.run_config.max_rounds
        self.stop_threshold = self.run_config.stop_threshold
        self.default_critic_role_prompt_file = self.run_config.default_critic_role_prompt_file
        self.default_refiner_role_prompt_file = self.run_config.default_refiner_role_prompt_file
        self.multi_critic_roles = self.run_config.multi_critic_roles
        self.disable_meta_critic = self.run_config.disable_meta_critic
        self.meta_critic_template = self.run_config.roles.get("meta_critic_template")
        self.full_config = self.run_config.full_config
        self.dry_run = self.run_config.dry_run
        self.run_log: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "original_user_prompt": None,
            "context_documents": [],  # Placeholder for future RAG
            "initial_generation": {},
            "critiques": [],
            "refinements": [],
            "reason_for_stopping": "",
            "final_output": "",
            "config_used": {
                "generator_model": self.generator_model,
                "critic_model": self.critic_model,
                "refiner_model": self.refiner_model,
                "max_rounds": self.max_rounds,
                "stop_on_no_actionable_critique_threshold": self.stop_threshold,
                "default_critic_role_prompt_file": self.default_critic_role_prompt_file,
                "default_refiner_role_prompt_file": self.default_refiner_role_prompt_file,
                "multi_critic_roles": self.multi_critic_roles,
                "disable_meta_critic": self.disable_meta_critic,
            },
        }


    async def _generate(
        self, initial_user_prompt: str, initial_content_for_review: Optional[str]
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates initial content; uses provided content or calls the generator model."""
        logging.info("Entering generation phase...")
        initial_response = initial_content_for_review or await call_model(
            prompt=f"User prompt: {initial_user_prompt}",
            model_name=self.generator_model,
            config=self.full_config,
            dry_run=self.dry_run,
            role="generator",
        )
        initial_generation_log = {
            "text": initial_response,
            "model_used": self.generator_model if initial_content_for_review is None else "N/A (provided content for review)",
        }
        logging.info(f"[{datetime.now().isoformat()}]\n--- Initial Response ---\n%s\n", initial_response)
        return initial_response, initial_generation_log

    async def _get_critique(self, current_text: str, role_file: str) -> str:
        """Helper function to get critique from a single role."""
        try:
            role_template = load_role_template(role_file)
            critique = await call_model(
                prompt=current_text,
                model_name=self.critic_model,
                system_prompt=role_template,
                config=self.full_config,
                dry_run=self.dry_run,
                role="critic",
            )
            return critique
        except ModelCallError as e:
            logging.error(f"[{datetime.now().isoformat()}] ModelCallError generating critique from {role_file}: {e}", exc_info=True)
            raise
        except Exception as e:
            logging.exception(f"[{datetime.now().isoformat()}] Unexpected error generating critique from {role_file}: {e}")
            raise

    async def _critique(
        self, current_text: str, round_num: int
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates a critique; handles single and multi-critic roles."""
        logging.info(f"[{datetime.now().isoformat()}] Entering critique phase (Round {round_num})...")
        critique_log = {"round": round_num, "model_used": self.critic_model}

        try:
            if self.multi_critic_roles:
                logging.info(
                    f"[{datetime.now().isoformat()}] --- Multi-agent Critique (Roles: %s) ---",
                    ", ".join(self.multi_critic_roles),
                )
                critiques = await asyncio.gather(
                    *[self._get_critique(current_text, role_file) for role_file in self.multi_critic_roles], timeout=60
                )
                critique = "\n\n".join(critiques)
                critique_log["role_prompt_file_used"] = self.multi_critic_roles
            else:
                critique = await self._get_critique(current_text, self.default_critic_role_prompt_file)
                critique_log["role_prompt_file_used"] = self.default_critic_role_prompt_file

            critique_log["text"] = critique
            logging.info(f"[{datetime.now().isoformat()}]\n--- Critique ---\n%s\n", critique)
            return critique, critique_log
        except asyncio.TimeoutError:
            logging.error(f"[{datetime.now().isoformat()}] Critique generation timed out.")
            raise
        except Exception as e:
            logging.exception(f"[{datetime.now().isoformat()}] Unexpected error during critique phase: {e}")
            raise


    async def _refine(
        self, current_text: str, critique: str, round_num: int
    ) -> Tuple[str, Dict[str, Any]]:
        """Refines the text based on the critique."""
        logging.info(f"[{datetime.now().isoformat()}] Entering refinement phase (Round {round_num})...")
        refine_prompt_for_model = (
            f"Original text:\n{current_text}\n\nCritique:\n{critique}\n\nRefine the original text based on the critique."
        )
        refined_response = await call_model(
            prompt=refine_prompt_for_model,
            model_name=self.refiner_model,
            system_prompt=self.run_config.roles.get("refiner_template"),
            config=self.full_config,
            dry_run=self.dry_run,
            role="refiner",
        )
        refinement_log = {
            "round": round_num,
            "text": refined_response,
            "model_used": self.refiner_model,
            "role_prompt_file_used": self.default_refiner_role_prompt_file,
        }
        logging.info(f"[{datetime.now().isoformat()}]\n--- Refined Response ---\n%s\n", refined_response)
        return refined_response, refinement_log

    async def _run_critique_refine_loop(self, initial_text: str) -> str:
        """Runs the iterative critique and refine loop."""
        current_text = initial_text
        for i in range(self.max_rounds):
            try:
                critique_text, critique_log = await self._critique(current_text, i + 1)
                self.run_log["critiques"].append(critique_log)

                if not self.disable_meta_critic:
                    actionability = await self._is_critique_actionable(critique_text)
                    if not actionability:
                        self.run_log["reason_for_stopping"] = (
                            f"Non-actionable critique received in round {i + 1}."
                        )
                        return current_text

                refined_response, refinement_log = await self._refine(
                    current_text, critique_text, i + 1
                )
                self.run_log["refinements"].append(refinement_log)
                current_text = refined_response
            except asyncio.TimeoutError:
                self.run_log["reason_for_stopping"] = f"Timeout in round {i+1}"
                return current_text
            except Exception as e:
                self.run_log["reason_for_stopping"] = f"Error in round {i+1}: {e}"
                logging.exception(f"[{datetime.now().isoformat()}] Error in _run_critique_refine_loop: {e}")
                return current_text
        return current_text

    async def _get_meta_critique(self, critique_text: str) -> Dict[str, Any]:
        """Gets meta-critique from the model."""
        if not self.meta_critic_template:
            logging.warning(f"[{datetime.now().isoformat()}] Meta-critic template not found. Assuming critique is actionable.")
            return {"actionable": True}
        try:
            response = await call_model(
                prompt=critique_text,
                model_name=self.run_config.meta_critic_model if hasattr(self.run_config, 'meta_critic_model') else self.critic_model, #Use specified meta-critic model if available, otherwise fallback to critic model.
                system_prompt=self.meta_critic_template,
                config=self.full_config,
                dry_run=self.dry_run,
                role="meta_critic",
            )
            if not isinstance(response, dict):
                raise ValueError(f"Unexpected response type from meta-critic model: {type(response)}")
            return response
        except (ModelCallError, ValueError) as e:
            logging.error(f"[{datetime.now().isoformat()}] Error during meta-critique: {e}", exc_info=True)
            return {"actionable": False}
        except Exception as e:
            logging.exception(f"[{datetime.now().isoformat()}] Unexpected error during meta-critique: {e}")
            return {"actionable": False}


    async def _is_critique_actionable(self, critique_text: str) -> bool:
        """Checks if the critique is actionable using a meta-critic model."""
        meta_critique_result = await self._get_meta_critique(critique_text)
        return meta_critique_result.get("actionable", False)


    async def run(
        self,
        initial_user_prompt: str,
        initial_content_for_review: Optional[str] = None,
    ) -> Tuple[str, Dict[Any, Any]]:
        """Runs the critique and refine loop."""
        self.run_log["original_user_prompt"] = initial_user_prompt
        start_time = time.time()

        try:
            initial_text, initial_generation_log = await self._generate(
                initial_user_prompt, initial_content_for_review
            )
            self.run_log["initial_generation"] = initial_generation_log
            final_text = await self._run_critique_refine_loop(initial_text)
            if not self.run_log["reason_for_stopping"]:
                self.run_log["reason_for_stopping"] = (
                    f"Max rounds ({self.max_rounds}) reached."
                )
            self.run_log["final_output"] = final_text
            self.run_log["runtime"] = time.time() - start_time

        except Exception as e:
            error_message = f"[{datetime.now().isoformat()}] Error during critique/refine loop: {e}"
            logging.exception(error_message)
            self.run_log["reason_for_stopping"] = error_message
            self.run_log["final_output"] = ""
            raise
        finally:
            self.logger.log_run(self.run_log)

        return self.run_log["final_output"], self.run_log

```
