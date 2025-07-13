import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
import logging
from pathlib import Path # Keep only one Path import

from core.model_router import call_model # Added call_model import
from core.roles import load_role_template # Added load_role_template import

from core.loop import CritiqueRefineLoop
from utils.config import (
    get_project_context_path,
    build_run_config,
    get_logging_config,
)
from utils.review_analyzer import ReviewAnalyzer  # Added import for ReviewAnalyzer


class SelfReviewTool:
    """A tool for self-reviewing code using a critique-refine loop."""

    def __init__(self, full_config: Dict[str, Any], output_dir: Optional[Path] = None):
        """Initialize the SelfReviewTool.

        Args:
            full_config: The full application configuration.
            output_dir: The directory to save review outputs. Defaults to 'reviews/self-improve'.
        """
        self.full_config = full_config
        self.logging_config = get_logging_config()
        if output_dir is None:
            self.output_dir = Path("reviews") / "self-improve"
        else:
            self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.review_analyzer = ReviewAnalyzer(self.output_dir)  # Initialize ReviewAnalyzer

    def _get_prior_review_context(self, num_reviews: int = 3) -> str:
        """Gets context from the most recent review files and tool improvement suggestions."""
        review_dir = Path("reviews") / "self-improve"
        if not review_dir.exists():
            return ""

        review_files = sorted(
            review_dir.glob("review_of_*.md"), key=os.path.getmtime, reverse=True
        )

        latest_reviews_content = []
        for review_file in review_files[:num_reviews]:
            try:
                latest_reviews_content.append(review_file.read_text(encoding="utf-8"))
            except IOError as e:
                logging.warning(f"Could not read review file {review_file}: {e}")

        tool_improvement_suggestions = self.review_analyzer.analyze_for_tool_improvement_suggestions()

        context_parts = []
        if latest_reviews_content:
            context_parts.append("--- PREVIOUS REVIEWS ---\n\n" + "\n\n---\n\n".join(latest_reviews_content))
        if tool_improvement_suggestions:
            context_parts.append("--- TOOL IMPROVEMENT SUGGESTIONS FROM PAST REVIEWS ---\n\n" + tool_improvement_suggestions)
        
        return "\n\n".join(context_parts)


    async def _load_file_content(self, file_path: Path) -> str:
        """Load the content of a file, prepending project context and prior review context.

        Args:
            file_path: The path to the file to load.

        Returns:
            The file content with project context and recent reviews prepended.

        Raises:
            FileNotFoundError: If the target file does not exist.
        """
        logging.info("Loading file content from: %s", file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Target file not found: {file_path}")

        content_to_review = file_path.read_text(encoding="utf-8")

        project_context_path = get_project_context_path()
        project_context = ""
        if project_context_path and project_context_path.exists():
            project_context = project_context_path.read_text(encoding="utf-8")
            logging.info("Loaded Project Context from %s", project_context_path)
        else:
            logging.warning(
                "Project context file not found at %s. Proceeding without context.",
                project_context_path,
            )

        prior_review_context = self._get_prior_review_context()

        # Prepend project context and prior review context to the content to be reviewed
        full_content_to_review = (
            f"{project_context}\n\n"
            f"{prior_review_context}\n\n"
            f"---\n\n{content_to_review}"
        )
        return full_content_to_review

    async def _run_review_loop(
        self, initial_content: str, review_config: Dict[str, Any], dry_run: bool
    ) -> Tuple[str, Dict[str, Any]]:
        """Run the critique-refine loop with the given content and arguments.

        Args:
            initial_content: The content to be reviewed.
            review_config: A dictionary of configuration options for the run.
            dry_run: If True, simulates the loop without actual model calls.

        Returns:
            A tuple containing the final refined output and the run log.
        """
        logging.info("Starting critique-refine loop for self-review.")
        run_config = build_run_config(review_config, self.full_config)
        run_config.dry_run = dry_run

        loop = CritiqueRefineLoop(run_config, strategy=review_config.get("strategy"))
        final_output, run_log = await loop.run(
            initial_user_prompt="",  # Not used in self-review mode
            initial_content_for_review=initial_content,
        )
        return final_output, run_log

    async def _save_output(
        self,
        original_file_path: Path,
        final_output: str,
        run_log: Dict[str, Any],
        save_improvement: bool,
    ) -> List[str]:
        """Save the review results to disk.

        This saves a Markdown review, a structured JSON log, and optionally a
        suggested code improvement file.

        Args:
            original_file_path: Path to the original file that was reviewed.
            final_output: The final refined text from the loop.
            run_log: The structured log of the critique-refine run.
            save_improvement: Whether to save the suggested improvement to a file.

        Returns:
            A list of strings describing the results of the save operations.
        """
        results = []
        current_timestamp = datetime.now()

        # Save Markdown review
        output_filename = (
            f"review_of_{original_file_path.name}_"
            f"{current_timestamp.strftime('%Y%m%d_%H%M%S')}.md"
        )
        output_filepath = self.output_dir / output_filename
        try:
            with open(output_filepath, "w", encoding="utf-8") as f:
                f.write(f"# Self-Review of {original_file_path}\n\n")
                f.write(f"**Timestamp:** {current_timestamp.isoformat()}\n\n")
                f.write(
                    f"**Original Content:**\n```\n"
                    f"{original_file_path.read_text(encoding='utf-8')}\n```\n\n"
                )
                f.write(f"**Critique-Refine Output:**\n{final_output}\n")
            results.append(f"Review saved to: {output_filepath}")
        except OSError as e:
            results.append(f"Error saving review to {output_filepath}: {e}")

        # Save structured JSON log
        log_filename = (
            f"log_of_{original_file_path.name}_"
            f"{current_timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        )
        log_filepath = self.output_dir / log_filename
        try:
            with open(log_filepath, "w", encoding="utf-8") as f:
                json.dump(run_log, f, indent=2)
            results.append(f"Structured log saved to: {log_filepath}")
        except (OSError, TypeError) as e:
            results.append(f"Error saving structured log to {log_filepath}: {e}")

        if save_improvement:
            suggested_filename = (
                f"{original_file_path.stem}.suggested{original_file_path.suffix}"
            )
            suggested_filepath = original_file_path.parent / suggested_filename
            try:
                with open(suggested_filepath, "w", encoding="utf-8") as f:
                    f.write(final_output)
                results.append(f"Suggested improvement saved to: {suggested_filepath}")
            except OSError as e:
                results.append(f"Error saving suggested improvement to {suggested_filepath}: {e}")
        return results

    async def _review_one_file(
        self,
        target_path: Path,
        save_improvement: bool,
        strategy_override: Optional[str],
        dry_run: bool,
    ) -> List[str]:
        """Run the complete self-review process for a single file.

        Args:
            target_path: The path to the file to review.
            save_improvement: Whether to save the suggested improvement.
            strategy_override: An optional strategy to override the default.
            dry_run: If True, simulates the run without saving files.

        Returns:
            A list of strings summarizing the outcome.
        """
        try:
            content_to_review = await self._load_file_content(target_path)
            print(f"\n--- Reviewing: {target_path} ---")

            # Create a configuration dictionary to pass to build_run_config
            self_review_config = self.full_config.get("self_review_config", {})
            review_config = {
                "strategy": strategy_override,
                "critic_role": self_review_config.get("default_critic_role"),
                "refiner_role": self_review_config.get("default_refiner_role"),
                "multi_critic_roles": None,
                "redact_logs": False,
                "save_improvement": save_improvement,
                "dry_run": dry_run,
            }

            final_output, run_log = await self._run_review_loop(
                content_to_review, review_config, dry_run
            )

            print(f"\n--- Final Output for {target_path} ---\n{final_output}\n")
            print(
                f"Reason for stopping: {run_log.get('reason_for_stopping', 'N/A')}\n"
            )

            if dry_run:
                return [f"Dry run mode for {target_path}: No files saved."]

            save_results = await self._save_output(
                target_path, final_output, run_log, save_improvement
            )

            # Run self-improvement critique after the main review is done
            self_improve_suggestions = await self._run_self_improvement_critique(
                target_path.name, content_to_review, final_output, run_log
            )
            if self_improve_suggestions:
                print(f"\n--- Self-Improvement Suggestions for the Tool ---\n{self_improve_suggestions}\n")
                save_results.append(f"Self-improvement suggestions generated for {target_path.name}.")

            return save_results
        except (FileNotFoundError, ValueError, IOError) as e:
            return [f"Error during self-review of {target_path}: {e}"]
        except Exception as e:
            logging.critical(
                "An unexpected error occurred during self-review of %s: %s",
                target_path,
                e,
                exc_info=True,
            )
            return [f"An unexpected error occurred during self-review of {target_path}: {e}"]

    async def _run_self_improvement_critique(
        self,
        original_file_name: str,
        original_content: str,
        final_output: str,
        run_log: Dict[str, Any],
    ) -> str:
        """
        Runs a critique specifically for self-improvement suggestions based on the review outcome.
        """
        logging.info("Running self-improvement critique for the tool.")
        
        # Prepare context for the self-improvement critic
        insights_summary = self.review_analyzer.analyze_for_tool_improvement_suggestions()
        
        prompt_content = (
            f"Review of file: {original_file_name}\n\n"
            f"Original content:\n{original_content}\n\n"
            f"Final refined output:\n{final_output}\n\n"
            f"Run log summary:\n{json.dumps(run_log, indent=2)}\n\n"
            f"Past review insights:\n{insights_summary}\n\n"
            f"Based on this information, provide concrete suggestions to improve the CritiqueRefineTool itself (e.g., adjust strategy parameters, suggest new roles, refine prompts)."
        )

        try:
            # Load the self-improvement critic template
            self_improve_template = load_role_template("self_improve_critic.txt")
            
            # Use a generic model for self-improvement critique (can be configured)
            # For simplicity, using generator_model here, but ideally it would be a dedicated model
            self_improve_critique = await call_model(
                prompt=prompt_content,
                model_name=self.full_config.get("critique_refine_config", {}).get("generator_model", "gemini-1.5-flash"), # Or a dedicated self_improve_model
                system_prompt=self_improve_template,
                config=self.full_config,
                dry_run=False, # Always run self-improvement critique, even in dry_run mode for main loop
                role="self_improve_critic",
            )
            return self_improve_critique
        except Exception as e:
            logging.error(f"Error during self-improvement critique: {e}", exc_info=True)
            return f"Error generating self-improvement suggestions: {e}"

    async def run(
        self,
        file_paths: List[Path],
        save_improvement: bool,
        strategy_override: Optional[str],
        dry_run: bool = False,
    ) -> str:
        """Run the self-review process for a list of files concurrently.

        Args:
            file_paths: A list of file paths to review.
            save_improvement: Whether to save suggested improvements.
            strategy_override: An optional strategy to override the default.
            dry_run: If True, simulates the run.

        Returns:
            A formatted string containing the results for all files.
        """
        logging.info("Starting self-review run for %d files.", len(file_paths))
        tasks = [
            self._review_one_file(
                path, save_improvement, strategy_override, dry_run
            )
            for path in file_paths
        ]
        results_nested = await asyncio.gather(*tasks)
        all_results = [item for sublist in results_nested for item in sublist]
        return "\n".join(all_results)
