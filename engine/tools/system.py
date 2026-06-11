import os
import glob
import subprocess
import json


def list_directory(params, context=None):
    path = params.get("path", ".")
    pattern = params.get("pattern", "*")
    recursive = params.get("recursive", False)

    if not os.path.exists(path):
        return {"status": "error", "message": f"Path not found: {path}"}

    full_pattern = os.path.join(path, "**" if recursive else "", pattern)
    files = glob.glob(full_pattern, recursive=recursive)
    files = [f for f in files if os.path.isfile(f)]
    files.sort()

    items = []
    for f in files:
        try:
            size = os.path.getsize(f)
            name = os.path.basename(f)
            items.append({"name": name, "path": f, "size": size})
        except OSError:
            continue

    return {
        "status": "ok",
        "message": f"Found {len(items)} file(s) in {path}",
        "files": items,
        "count": len(items),
    }


def run_command(params, context=None):
    command = params.get("command", "")
    if not command:
        return {"status": "error", "message": "No command provided"}

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=params.get("timeout", 30),
        )
        output = result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        return {
            "status": "ok",
            "message": f"Command completed with return code {result.returncode}",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "output": output,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Command timed out"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def register_system_tools(registry):
    registry.register(
        "list_directory",
        list_directory,
        "LIST files in a directory. params: path, pattern (glob), recursive (bool)",
    )
    registry.register(
        "run_command",
        run_command,
        "RUN a system command (shell). params: command, timeout (seconds)",
    )
