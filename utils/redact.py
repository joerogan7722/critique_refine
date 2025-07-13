import re
import copy
from typing import Any, List, Tuple

def _redact_dict_recursive(
    data: Any,
    keys_to_redact: List[str],
    patterns: List[Tuple[str, str]],
) -> Any:
    """
    Recursively walks nested dictionaries and lists to redact sensitive data.

    It redacts based on both sensitive keys and regex patterns.
    Operates on a deep copy of the input data.
    """
    # Deep copy to avoid modifying the original dictionary in place
    data = copy.deepcopy(data)

    if isinstance(data, dict):
        for key, value in data.items():
            if key in keys_to_redact:
                data[key] = f"[REDACTED_{key.upper()}]"
            else:
                data[key] = _redact_dict_recursive(value, keys_to_redact, patterns)
    elif isinstance(data, list):
        return [
            _redact_dict_recursive(item, keys_to_redact, patterns) for item in data
        ]
    elif isinstance(data, str):
        redacted_text = data
        for pattern, replacement in patterns:
            redacted_text = re.sub(pattern, replacement, redacted_text, flags=re.IGNORECASE)
        return redacted_text

    return data
