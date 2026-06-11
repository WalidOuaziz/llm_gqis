import json
import os
from pathlib import Path

DESTRUCTIVE_TOOLS = {
    "remove_layer",
    "delete_file",
    "overwrite_layer",
    "remove_project",
    "delete_field",
    "clear_project",
}

DANGEROUS_KEYWORDS = ["DELETE", "DROP", "TRUNCATE", "ALTER", "EXEC", "SYSTEM"]

BLOCKED_PATHS = [
    str(Path(os.environ.get("SYSTEMROOT", "C:\\Windows"))),
    str(Path(os.environ.get("PROGRAMFILES", "C:\\Program Files"))),
    str(Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))),
]


def validate_plan_schema(plan):
    if not isinstance(plan, dict):
        return False, "Plan must be a JSON object"
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return False, "Plan must contain a 'steps' array"
    if not steps:
        return True, None
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"Step {i} is not an object"
        if "tool" not in step:
            return False, f"Step {i} missing required 'tool' field"
        if not isinstance(step["tool"], str) or not step["tool"].strip():
            return False, f"Step {i} has invalid 'tool'"
        if "parameters" in step and not isinstance(step["parameters"], dict):
            return False, f"Step {i} 'parameters' must be an object"
    return True, None


def check_destructive(tool_name, parameters):
    if tool_name in DESTRUCTIVE_TOOLS:
        return True, f"Destructive operation '{tool_name}' requires confirmation: {json.dumps(parameters)}"
    return False, None


def validate_file_path(filepath):
    try:
        p = Path(filepath).resolve()
        for blocked in BLOCKED_PATHS:
            try:
                str(p).startswith(blocked)
            except Exception:
                pass
        return True, str(p)
    except Exception as e:
        return False, str(e)


def sanitize_layer_name(name):
    import re
    return re.sub(r"[^\w\- ]", "", name).strip()


def validate_expression(expression):
    if not isinstance(expression, str):
        return False, "Expression must be a string"
    upper = expression.upper()
    for kw in DANGEROUS_KEYWORDS:
        if kw in upper:
            return False, f"Expression contains dangerous keyword: {kw}"
    return True, None
