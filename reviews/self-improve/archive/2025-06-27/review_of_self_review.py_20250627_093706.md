# Self-Review of core\self_review.py

**Timestamp:** 2025-06-27T09:37:06.138622

**Original Content:**
```
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import argparse

from core.loop import CritiqueRefineLoop
from utils.config import (
    get_project_context_path,
    build_run_config,
    get_logging_config,
)


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

    async def _load_file_content(self, file_path: Path) -> str:
        """Load the content of a file, prepending project context if available.

        Args:
            file_path: The path to the file to load.

        Returns:
            The file content with project context prepended.

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

        # Prepend project context to the content to be reviewed
        full_content_to_review = f"{project_context}\n\n---\n\n{content_to_review}"
        return full_content_to_review

    async def _run_review_loop(
        self, initial_content: str, args: Any, dry_run: bool
    ) -> Tuple[str, Dict[str, Any]]:
        """Run the critique-refine loop with the given content and arguments.

        Args:
            initial_content: The content to be reviewed.
            args: Command-line arguments to configure the run.
            dry_run: If True, simulates the loop without actual model calls.

        Returns:
            A tuple containing the final refined output and the run log.
        """
        logging.info("Starting critique-refine loop for self-review.")
        run_config = build_run_config(args, self.full_config)
        run_config.dry_run = dry_run

        loop = CritiqueRefineLoop(run_config)
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

            # Create a mock args object to pass to build_run_config
            mock_args = argparse.Namespace(
                strategy=strategy_override,
                critic_role=None,
                refiner_role=None,
                multi_critic_roles=None,
                redact_logs=False,
                save_improvement=save_improvement,
                dry_run=dry_run,
            )

            final_output, run_log = await self._run_review_loop(
                content_to_review, mock_args, dry_run
            )

            print(f"\n--- Final Output for {target_path} ---\n{final_output}\n")
            print(
                f"Reason for stopping: {run_log.get('reason_for_stopping', 'N/A')}\n"
            )

            if dry_run:
                return [f"Dry run mode for {target_path}: No files saved."]

            return await self._save_output(
                target_path, final_output, run_log, save_improvement
            )
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

```

**Critique-Refine Output:**
```python
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import logging
import argparse
from jsonschema import validate, ValidationError

from core.loop import CritiqueRefineLoop
from utils.config import (
    get_project_context_path,
    build_run_config,
    get_logging_config,
)


# Define a schema for configuration validation using jsonschema
schema = {
    "type": "object",
    "properties": {
        "models": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "path": {"type": "string"},
                    # Add other model-specific properties as needed
                },
                "required": ["name", "path"],
            },
            "minItems": 1,
        },
        "max_iterations": {"type": "integer", "minimum": 1},
        # Add other configuration properties and their schemas here
    },
    "required": ["models"],
}


def validate_config(config: Dict[str, Any]) -> None:
    """Validates the application configuration against a predefined schema.

    Args:
        config: The application configuration dictionary.

    Raises:
        ValueError: If the configuration is invalid.
    """
    try:
        validate(instance=config, schema=schema)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}") from None


class SelfReviewTool:
    """A tool for self-reviewing code using a critique-refine loop."""

    def __init__(self, full_config: Dict[str, Any], output_dir: Optional[Path] = None):
        """Initialize the SelfReviewTool.

        Args:
            full_config: The full application configuration. Must contain a valid 'models' section.
            output_dir: The directory to save review outputs. Defaults to 'reviews/self-improve'.

        Raises:
            ValueError: If the configuration is invalid.
        """
        validate_config(full_config)  # Raise ValueError if invalid
        self.full_config = full_config
        self.logging_config = get_logging_config()
        self.output_dir = output_dir or Path("reviews") / "self-improve"
        self.output_dir.mkdir(parents=True, exist_ok=True)


    async def _load_file_content(self, file_path: Path) -> str:
        """Load the content of a file.

        Args:
            file_path: The path to the file to load.

        Returns:
            The file content.

        Raises:
            FileNotFoundError: If the target file does not exist.
        """
        logging.debug("Loading file content from: %s (size: %s bytes)", file_path, file_path.stat().st_size)
        if not file_path.exists():
            raise FileNotFoundError(f"Target file not found: {file_path}")
        return file_path.read_text(encoding="utf-8")


    async def _run_review_loop(self, initial_content: str, args: argparse.Namespace, dry_run: bool) -> Tuple[str, Dict[str, Any]]:
        """Run the critique-refine loop with the given content and arguments.

        Args:
            initial_content: The content to be reviewed.
            args: Command-line arguments to configure the run.
            dry_run: If True, simulates the loop without actual model calls.

        Returns:
            A tuple containing the final refined output and the run log.
        """
        logging.info("Starting critique-refine loop for self-review.")
        run_config = build_run_config(vars(args), self.full_config)
        run_config["dry_run"] = dry_run
        loop = CritiqueRefineLoop(run_config)
        final_output, run_log = await loop.run(initial_content_for_review=initial_content)
        return final_output, run_log


    def _save_file(self, filepath: Path, content: str) -> Tuple[bool, str]:
        """Helper function to save content to a file."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True, ""
        except OSError as e:
            return False, str(e)
        except json.JSONDecodeError as e:
            return False, f"JSON decoding error: {e}"
        except Exception as e:
            logging.exception("Unexpected error saving file %s: %s", filepath, e)
            return False, str(e)


    async def _save_markdown_review(self, original_file_path: Path, final_output: str, run_log: Dict[str, Any]) -> Tuple[bool, str, Path]:
        """Saves the markdown review file using a template for better readability."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"review_of_{original_file_path.name}_{timestamp}.md"
        output_filepath = self.output_dir / output_filename
        #Improved markdown generation using f-strings for better clarity.
        markdown_content = f"""# Self-Review of {original_file_path}

**Timestamp:** {datetime.now().isoformat()}

**Original Content:**
```
{original_file_path.read_text(encoding='utf-8')}
```

**Critique-Refine Output:**
{final_output}

**Run Log:**
```json
{json.dumps(run_log, indent=2)}
```
"""
        success, message = self._save_file(output_filepath, markdown_content)
        return success, message, output_filepath


    async def _save_structured_log(self, original_file_path: Path, run_log: Dict[str, Any]) -> Tuple[bool, str, Path]:
        """Saves the structured JSON log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"log_of_{original_file_path.name}_{timestamp}.json"
        log_filepath = self.output_dir / log_filename
        project_context_path = get_project_context_path()
        if project_context_path and project_context_path.exists():
            try:
                project_context = project_context_path.read_text(encoding="utf-8")
                run_log["project_context"] = project_context #Store the content itself instead of just path
            except Exception as e:
                logging.error("Error reading project context file: %s", e)
        else:
            logging.warning("Project context file not found. Proceeding without context.")
        success, message = self._save_file(log_filepath, json.dumps(run_log, indent=2))
        return success, message, log_filepath


    async def _save_suggested_improvement(self, original_file_path: Path, final_output: str) -> Tuple[bool, str, Path]:
        """Saves the suggested improvement file."""
        suggested_filename = f"{original_file_path.stem}.suggested{original_file_path.suffix}"
        suggested_filepath = original_file_path.parent / suggested_filename
        success, message = self._save_file(suggested_filepath, final_output)
        return success, message, suggested_filepath


    async def _save_output(
        self,
        original_file_path: Path,
        final_output: str,
        run_log: Dict[str, Any],
        save_improvement: bool,
    ) -> List[str]:
        """Save the review results to disk."""
        save_functions = [
            (self._save_markdown_review, (original_file_path, final_output, run_log)),
            (self._save_structured_log, (original_file_path, run_log)),
        ]
        if save_improvement:
            save_functions.append((self._save_suggested_improvement, (original_file_path, final_output)))

        results = []
        for func, args in save_functions:
            success, message, path = await func(*args)
            results.append(f"{'Success' if success else 'Error'} saving to {path}: {message}")
        return results


    async def _review_one_file(
        self,
        target_path: Path,
        args: argparse.Namespace,
        save_improvement: bool,
    ) -> List[str]:
        """Run the complete self-review process for a single file."""
        try:
            content_to_review = await self._load_file_content(target_path)
            logging.info("Starting review for %s", target_path)
            print(f"\n--- Reviewing: {target_path} ---")
            final_output, run_log = await self._run_review_loop(
                content_to_review, args, args.dry_run
            )
            print(f"\n--- Final Output for {target_path} ---\n{final_output}\n")
            print(
                f"Reason for stopping: {run_log.get('reason_for_stopping', 'N/A')}\n"
            )

            if args.dry_run:
                return [f"Dry run mode for {target_path}: No files saved."]

            return await self._save_output(
                target_path, final_output, run_log, save_improvement
            )
        except FileNotFoundError as e:
            return [f"Error during self-review of {target_path}: File not found - {e}"]
        except OSError as e:
            return [f"Error during self-review of {target_path}: I/O Error - {e}"]
        except Exception as e:
            logging.exception(
                "An unexpected error occurred during self-review of %s", target_path
            )
            return [f"An unexpected error occurred during self-review of {target_path}: {e}"]


    async def run(
        self,
        file_paths: List[Path],
        args: argparse.Namespace,
        save_improvement: bool,
    ) -> str:
        """Run the self-review process for a list of files concurrently."""
        logging.info("Starting self-review run for %d files.", len(file_paths))
        results = []
        try:
            tasks = [self._review_one_file(path, args, save_improvement) for path in file_paths]
            for task in asyncio.as_completed(tasks): #Handles errors and completes successfully running tasks
                result = await task
                results.extend(result)
        except Exception as e:
            logging.exception("A critical error occurred during the self-review process")
            results.append(f"Critical error during self-review: {e}")

        return "\n".join(results)



# Example Argument Parser Setup
def create_parser():
    parser = argparse.ArgumentParser(description="Self-review code tool.")
    parser.add_argument("files", nargs="+", type=Path, help="Paths to the files to review.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate the review without actual model calls.")
    parser.add_argument("--save-improvement", action="store_true", help="Save the suggested improvements to files.")
    parser.add_argument("--config", type=Path, required=True, help="Path to the configuration file.")
    return parser


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    with open(args.config, 'r') as f:
        config = json.load(f)

    logging.basicConfig(**get_logging_config())
    tool = SelfReviewTool(config)
    asyncio.run(tool.run(args.files, args, args.save_improvement))

```
