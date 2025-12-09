import re
from dataclasses import dataclass
from typing import Any, Generic, Mapping, TypeVar

T = TypeVar("T", str, dict[str, Any])


@dataclass
class ReplaceResult(Generic[T]):
    replaced: T
    replaced_variables: set[str]
    missing_variables: set[str]

    @property
    def total_variables(self) -> int:
        return len(self.replaced_variables) + len(self.missing_variables)


def replace_variables(template: dict[str, Any], variables: Mapping[str, str]) -> ReplaceResult[dict[str, Any]]:
    """Recursively replace variables in all string values within a dict."""
    all_replaced_vars = set()
    all_missing_vars = set()

    def process_value(value: Any) -> Any:
        """Process a value, replacing variables if it's a string or recursing if it's a container."""
        if isinstance(value, str):
            result = _replace_variables(value, variables)
            all_replaced_vars.update(result.replaced_variables)
            all_missing_vars.update(result.missing_variables)
            return result.replaced
        elif isinstance(value, dict):
            processed_dict = {}
            for k, v in value.items():
                processed_dict[k] = process_value(v)
            return processed_dict
        elif isinstance(value, list):
            return [process_value(item) for item in value]
        else:
            # Return non-string, non-container values unchanged
            return value

    return ReplaceResult(
        replaced=process_value(template),
        replaced_variables=all_replaced_vars,
        missing_variables=all_missing_vars,
    )


def _replace_variables(template: str, variables: Mapping[str, str]) -> ReplaceResult[str]:
    """Replace variables of pattern ${VAR_NAME} with values from dict."""
    # Find all variable patterns (a-zA-Z0-9_)
    pattern = r"\$\{([a-zA-Z0-9_]+)\}"
    matches = re.findall(pattern, template)

    # Track what we've seen
    found_vars = set(matches)
    replaced_vars = set()
    missing_vars = set()

    # Replace variables
    rendered = template
    for var_name in found_vars:
        if var_name in variables:
            rendered = rendered.replace(f"${{{var_name}}}", variables[var_name])
            replaced_vars.add(var_name)
        else:
            missing_vars.add(var_name)

    return ReplaceResult(
        replaced=rendered,
        replaced_variables=replaced_vars,
        missing_variables=missing_vars,
    )
