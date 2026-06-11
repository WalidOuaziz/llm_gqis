import json
import re


def _fix_unquoted_keys(text):
    """Add quotes to unquoted object keys, only when outside JSON strings."""
    result = []
    in_string = False
    escape = False
    i = 0
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            result.append(c)
            i += 1
            continue
        if c == '\\':
            escape = True
            result.append(c)
            i += 1
            continue
        if c == '"':
            in_string = not in_string
            result.append(c)
            i += 1
            continue
        if not in_string and (c.isalnum() or c == '_'):
            start = i
            while i < len(text) and (text[i].isalnum() or text[i] == '_'):
                i += 1
            key = text[start:i]
            j = i
            while j < len(text) and text[j] in ' \t\n\r':
                j += 1
            if j < len(text) and text[j] == ':':
                result.append('"' + key + '"')
            else:
                result.append(key)
            continue
        result.append(c)
        i += 1
    return ''.join(result)


def _fix_backslashes(text):
    """Replace backslashes that look like Windows path separators with forward slashes.
    Preserves valid JSON escapes: \\\\, \\", \\/, \\uXXXX.
    Converts all other \\X (literal backslash + char) to /X,
    including \\f, \\b, \\n, \\r, \\t which are valid JSON escapes
    but overwhelmingly appear as path separators in LLM output."""
    result = []
    i = 0
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt in ('"', '\\', '/'):
                result.append(text[i:i+2])
                i += 2
            elif nxt == 'u' and i + 5 < len(text):
                hex_part = text[i+2:i+6]
                if all(c in '0123456789abcdefABCDEF' for c in hex_part):
                    result.append(text[i:i+6])
                    i += 6
                else:
                    result.append('/')
                    i += 1
            else:
                result.append('/')
                i += 1
        else:
            result.append(text[i])
            i += 1
    return ''.join(result)


def _repair_json(text):
    text = text.strip()
    if not text:
        return text

    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    text = re.sub(r"(?<!\\)\'(.*?)\'(?=\s*[:,\}\]])", r'"\1"', text)
    text = re.sub(r"(?<!\\)\'", '"', text)

    text = _fix_unquoted_keys(text)

    text = re.sub(r"\.0+(?=\s*[,\}\]])", ".0", text)

    text = re.sub(r",\s*}", "}", text)
    text = re.sub(r",\s*]", "]", text)

    text = re.sub(r"True", "true", text)
    text = re.sub(r"False", "false", text)
    text = re.sub(r"None", "null", text)

    text = re.sub(r"\\/", "/", text)

    text = _fix_backslashes(text)

    return text


def _try_parse(s):
    if not s:
        raise json.JSONDecodeError("empty", s, 0)
    try:
        repaired = _repair_json(s)
        return json.loads(repaired)
    except json.JSONDecodeError:
        raise


def _extract_code_blocks(text):
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
    return [b.strip() for b in blocks if b.strip()]


def _find_json_objects(text):
    """Find all potential JSON objects/arrays in text and return the first valid one."""
    results = []

    for m in re.finditer(r"(\{[\s\S]*?\}|\[[\s\S]*?\])", text):
        candidate = m.group(0)
        try:
            parsed = _try_parse(candidate)
            results.append(parsed)
        except (json.JSONDecodeError, ValueError):
            continue

    return results


def _find_best_json_span(text):
    """Find the longest valid JSON span by trying parse from each { or [."""
    start_positions = []
    for i, ch in enumerate(text):
        if ch in ("{", "["):
            start_positions.append((i, ch))

    best = None
    best_len = 0

    for start, ch in start_positions:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c in ("{", "["):
                depth += 1
            elif c in ("}", "]"):
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        parsed = _try_parse(candidate)
                        if len(candidate) > best_len:
                            best = parsed
                            best_len = len(candidate)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    return best


def extract_json_from_text(text):
    if not text or not text.strip():
        raise json.JSONDecodeError("Empty response", text, 0)

    code_blocks = _extract_code_blocks(text)
    for block in code_blocks:
        try:
            return _try_parse(block)
        except (json.JSONDecodeError, ValueError):
            continue

    result = _find_best_json_span(text)
    if result is not None:
        return result

    simple_objects = _find_json_objects(text)
    if simple_objects:
        longest = max(simple_objects, key=lambda x: len(json.dumps(x, ensure_ascii=False)))
        return longest

    text = text.strip()
    try:
        return _try_parse(text)
    except (json.JSONDecodeError, ValueError):
        raise json.JSONDecodeError("No valid JSON found in response", text, 0)


def parse_llm_response(response_text):
    raw_preview = response_text[:600] if response_text else "(empty)"

    try:
        result = extract_json_from_text(response_text)
    except json.JSONDecodeError as e:
        return None, f"Failed to parse JSON from LLM response. Raw response preview: {raw_preview}"

    if isinstance(result, list):
        result = {"steps": result}

    if not isinstance(result, dict):
        return None, f"Parsed result is not an object or array. Raw: {raw_preview}"

    if "steps" not in result:
        if "plan" in result:
            result["steps"] = result["plan"]
            del result["plan"]
        elif "actions" in result:
            result["steps"] = result["actions"]
            del result["actions"]
        elif "commands" in result:
            result["steps"] = result["commands"]
            del result["commands"]
        elif isinstance(result.get("tool"), str):
            result = {"steps": [result]}
        else:
            flat = []
            for key, val in result.items():
                if isinstance(val, dict):
                    step = {"tool": key}
                    step["parameters"] = val if val else {}
                    flat.append(step)
            if flat:
                result = {"steps": flat}
            else:
                return None, f"Response has no 'steps' array. Keys: {list(result.keys())}. Raw: {raw_preview}"

    steps = result["steps"]
    if not isinstance(steps, list):
        return None, f"'steps' is not a list. Raw: {raw_preview}"

    normalized = []
    for i, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        tool = s.get("tool") or s.get("action") or s.get("name") or s.get("function") or s.get("command")
        if not tool:
            continue
        params = s.get("parameters") or s.get("params") or s.get("arguments") or s.get("args") or {}
        if not isinstance(params, dict):
            try:
                params = dict(params)
            except (TypeError, ValueError):
                params = {}
        normalized.append({"tool": tool, "parameters": params})

    if not normalized:
        return {"steps": []}, None

    result["steps"] = normalized
    return result, None
