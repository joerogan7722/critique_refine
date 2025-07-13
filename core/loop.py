import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import time
import yaml  # Moved to top of file

# Local imports
from .model_router import call_model, ModelCallError
from .roles import load_role_template, TemplateNotFoundError
from ..utils.logger import Logger
from .config import RunConfig


class CritiqueRefineLoop:
    """Encapsulates the critique and refinement loop logic."""

    def __init__(self, run_config: RunConfig, strategy: Optional[str] = None):
        """Initializes the loop with a run configuration.

        Args:
            run_config: The configuration for this loop instance.
            strategy: The name of the strategy to use.
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
        self.strategy = self._load_strategy(strategy)
        self.run_log: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "original_user_prompt": None,
            "context_documents": [],
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

    def _load_strategy(self, strategy_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Loads a strategy from the strategies.yaml file."""
        if not strategy_name:
            return None
        try:
            with open("strategies.yaml", "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data.get("strategies", {}).get(strategy_name)
        except (FileNotFoundError, yaml.YAMLError) as e:
            logging.error(f"Could not load or parse strategies.yaml: {e}")
            return None

    async def _critique(
        self, current_text: str, round_num: int
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates a critique; handles single and multi-critic roles."""
        logging.info(f"[{datetime.now().isoformat()}] Entering critique phase (Round {round_num})...")
        critique_log = {"round": round_num, "model_used": self.critic_model}

        try:
            roles_to_use = []
            if self.strategy:
                if isinstance(self.strategy, list):
                    roles_to_use = [f"{role}.txt" for role in self.strategy]
                elif isinstance(self.strategy, dict) and "roles" in self.strategy:
                    roles_to_use = [f"{role}.txt" for role in self.strategy["roles"]]
            elif self.multi_critic_roles:
                roles_to_use = self.multi_critic_roles
            elif self.default_critic_role_prompt_file:
                roles_to_use = [self.default_critic_role_prompt_file]
            else:
                raise ValueError("No critic role specified in the configuration.")

            logging.debug(f"[_critique] roles_to_use: {roles_to_use}")
            logging.info(
                f"[{datetime.now().isoformat()}] --- Multi-agent Critique (Roles: %s) ---",
                ", ".join(roles_to_use),
            )
            critiques = await asyncio.gather(
                *[self._get_critique(current_text, role_file) for role_file in roles_to_use]
            )
            logging.debug(f"[_critique] critiques from asyncio.gather: {critiques}")
            critique = "\n\n".join(critiques)
            critique_log["role_prompt_file_used"] = roles_to_use
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
                self.run_log["reason_for_stopping"] = f"Timeout in round {i + 1}"
                return current_text
            except (TemplateNotFoundError, ValueError):
                raise  # Re-raise to be caught by the main run loop's handler
            except Exception as e:
                # Log and set reason for stopping only in the main run method's finally block
                self.run_log["reason_for_stopping"] = f"Error in round {i + 1}: {e}"
                # Removed logging.exception here to prevent duplicate logging
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
                model_name=self.run_config.meta_critic_model,
                system_prompt=self.meta_critic_template,
                config=self.full_config,
                dry_run=self.dry_run,
                role="meta_critic",
            )
            if isinstance(response, str):
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # Handle cases where the string is not valid JSON
                    return {"actionable": "ACTIONABLE" in response}
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

    async def _run_brainstormer_loop(self, initial_text: str) -> str:
        """Runs the brainstormer loop for a specified number of rounds."""
        current_text = initial_text
        logging.debug(f"[_run_brainstormer_loop] self.strategy: {self.strategy}")
        if self.strategy and (
            (isinstance(self.strategy, list) and "brainstormer" in self.strategy)
            or (
                isinstance(self.strategy, dict)
                and "brainstormer" in self.strategy.get("roles", [])
            )
        ):
            logging.debug("[_run_brainstormer_loop] Strategy condition met.")
            brainstormer_rounds = 1
            if isinstance(self.strategy, dict):
                brainstormer_rounds = self.strategy.get("max_rounds", 1)
            for i in range(brainstormer_rounds):
                logging.info(f"Entering brainstormer phase (Round {i + 1})...")
                brainstormer_template = load_role_template("brainstormer.txt")
                current_text = await call_model(
                    prompt=current_text,
                    model_name=self.generator_model,
                    system_prompt=brainstormer_template,
                    config=self.full_config,
                    dry_run=self.dry_run,
                    role="brainstormer",
                )
                logging.info(f"--- Brainstormer Response ---\n{current_text}\n")
                logging.debug(f"[_run_brainstormer_loop] current_text after call_model: {current_text}")
            return current_text
        logging.debug("[_run_brainstormer_loop] Strategy condition NOT met. Returning initial_text.")
        return initial_text

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

            # Run brainstormer loop if applicable
            brainstormed_text = await self._run_brainstormer_loop(initial_text)

            final_text = await self._run_critique_refine_loop(brainstormed_text)
            if not self.run_log["reason_for_stopping"]:
                self.run_log["reason_for_stopping"] = (
                    f"Max rounds ({self.max_rounds}) reached."
                )
            self.run_log["final_output"] = final_text
            self.run_log["runtime"] = time.time() - start_time

        except (TemplateNotFoundError, asyncio.TimeoutError) as e:
            logging.error(f"[{datetime.now().isoformat()}] Error during loop execution: {e}", exc_info=True)
            self.run_log["reason_for_stopping"] = f"Error: {e}"
            self.run_log["final_output"] = ""
            self.logger.log_run(self.run_log)
            raise
        except Exception as e:
            error_message = f"[{datetime.now().isoformat()}] Error during critique/refine loop: {e}"
            logging.exception(error_message)
            self.run_log["reason_for_stopping"] = error_message
            self.run_log["final_output"] = ""
            raise
        finally:
            self.logger.log_run(self.run_log)

        return self.run_log["final_output"], self.run_log
