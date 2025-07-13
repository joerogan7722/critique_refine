import json
from pathlib import Path
from typing import Dict, Any, List, Optional

class ReviewAnalyzer:
    """Analyzes past review logs to extract insights for self-improvement."""

    def __init__(self, log_directory: Path):
        self.log_directory = log_directory

    def _load_log_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Loads a single JSON log file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None

    def get_recent_insights(self, num_logs: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieves and analyzes the most recent review logs.

        Returns a list of dictionaries, each containing a summary of a log.
        """
        insights = []
        log_files = sorted(
            self.log_directory.glob("log_of_*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        for log_file in log_files[:num_logs]:
            log_data = self._load_log_file(log_file)
            if log_data:
                insight = {
                    "timestamp": log_data.get("timestamp"),
                    "original_user_prompt": log_data.get("original_user_prompt"),
                    "final_output_summary": log_data.get("final_output", "")[:200] + "...",  # Truncate for summary
                    "reason_for_stopping": log_data.get("reason_for_stopping"),
                    "critiques_summary": [
                        c.get("text", "")[:100] + "..." for c in log_data.get("critiques", [])
                    ],
                    "refinements_summary": [
                        r.get("text", "")[:100] + "..." for r in log_data.get("refinements", [])
                    ],
                    "config_used": log_data.get("config_used"),
                }
                insights.append(insight)
        return insights

    def analyze_for_tool_improvement_suggestions(self, num_logs: int = 5) -> str:
        """
        Analyzes recent logs to suggest improvements for the tool itself.
        This is a simplified example; real analysis would be more complex.
        """
        insights = self.get_recent_insights(num_logs)
        suggestions = []

        if not insights:
            return "No past review logs found for analysis."

        # Example: Look for common reasons for stopping
        stop_reasons_count = {}
        for insight in insights:
            reason = insight.get("reason_for_stopping")
            if reason:
                stop_reasons_count[reason] = stop_reasons_count.get(reason, 0) + 1
        
        most_common_stop_reason = None
        if stop_reasons_count:
            # Ensure the key is callable for max function
            most_common_stop_reason = max(stop_reasons_count, key=lambda k: stop_reasons_count.get(k, 0))
            suggestions.append(f"- The most common reason for stopping in recent runs was: '{most_common_stop_reason}'. Consider ways to address this, e.g., by adjusting `max_rounds` or `stop_threshold`, or improving relevant role prompts.")

        # Example: Look for short critiques (might indicate lack of detail)
        short_critiques_found = False
        for insight in insights:
            for critique_summary in insight.get("critiques_summary", []):
                if len(critique_summary) < 50:  # Arbitrary threshold for "short"
                    short_critiques_found = True
                    break
            if short_critiques_found:
                break
        if short_critiques_found:
            suggestions.append("- Some critiques appear to be very short. Review the 'meta_critic' prompt or critic role prompts to encourage more detailed and actionable feedback.")

        if not suggestions:
            return "Analysis of recent logs did not reveal immediate tool improvement suggestions."
        
        return "Based on recent review logs, here are some potential areas for tool improvement:\n" + "\n".join(suggestions)
