import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .redact import _redact_dict_recursive


class Logger:
    """Handles logging of structured run data to a JSONL file."""

    def __init__(
        self,
        log_file_path: str,
        redact: bool = False,
        keys_to_redact: Optional[List[str]] = None,
        redaction_patterns: Optional[List[tuple[str, str]]] = None,
    ):
        """Initialize the Logger.

        Args:
            log_file_path: The path to the log file.
            redact: Whether to redact sensitive information.
            keys_to_redact: A list of keys to redact from the log.
            redaction_patterns: A list of regex patterns to redact.
        """
        self.log_file = Path(log_file_path)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.redact = redact
        self.keys_to_redact = keys_to_redact or []
        self.redaction_patterns = redaction_patterns or []

    def log_run(self, log_entry: Dict[str, Any]):
        """Log a single run entry, redacting if configured.

        Args:
            log_entry: The dictionary containing the log data for the run.
        """
        entry_to_log = (
            _redact_dict_recursive(
                log_entry,
                keys_to_redact=self.keys_to_redact,
                patterns=self.redaction_patterns,
            )
            if self.redact
            else log_entry
        )

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_to_log) + "\n")
