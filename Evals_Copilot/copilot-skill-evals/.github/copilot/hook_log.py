#!/usr/bin/env python3
"""Audit-log writer for GitHub Copilot hooks.

This is the Copilot analog of Kiro's hook scripts. Copilot fires lifecycle hooks
(configured in .github/hooks/*.json) and pipes a JSON payload to the hook command
on stdin. This script reads that payload and appends a single line to audit.log
in the SAME format Kiro's hooks produced, so process_assert.py / context_assert.py
work unchanged:

    [YYYY-MM-DD HH:MM:SS] READ  <path>
    [YYYY-MM-DD HH:MM:SS] WRITE <path>
    [YYYY-MM-DD HH:MM:SS] SHELL <command>
    [YYYY-MM-DD HH:MM:SS] SKILL <prompt-file / slash-command>
    [YYYY-MM-DD HH:MM:SS] STEERING <instruction-file-path>

Invoked by .github/hooks/audit.json for these events:
    --event tool      postToolUse       -> READ / WRITE / SHELL (+ SKILL/STEERING sub-detection)
    --event prompt    userPromptSubmitted -> SKILL (leading /slash-command)
    --event session   sessionStart      -> STEERING (scan active instruction files, deduped per day)

stdin payload (Copilot CLI native format, camelCase):
    { "sessionId", "timestamp", "cwd", "toolName", "toolArgs": {...}, "toolResult": {...} }

Tool names: view (read), create/edit (write), bash/powershell (shell), grep/glob (search).

The exact key inside toolArgs holding the path/command is not fully documented and
can vary by version, so PATH_KEYS / COMMAND_KEYS below try the common names and
fall back to a heuristic. Run any hook with COPILOT_EVALS_DEBUG=1 to append the
raw payload to hook_debug.log for one-time calibration.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent


def workspace_root() -> Path:
    # THIS_DIR = <root>/.github/copilot ; parents[0]=.github ; parents[1]=<root>
    return THIS_DIR.parents[1]


def audit_log_path() -> Path:
    env = os.environ.get("COPILOT_EVALS_AUDIT_LOG")
    if env:
        return Path(env)
    return workspace_root() / "audit.log"


# Candidate keys inside toolArgs for a file path / a shell command.
PATH_KEYS = ("path", "filePath", "file", "filename", "fileName", "absolutePath", "target", "targetFile")
COMMAND_KEYS = ("command", "cmd", "script", "commandLine")

TOOL_EVENT_MAP = {
    "view": "READ",
    "read": "READ",
    "grep": "READ",
    "glob": "READ",
    "create": "WRITE",
    "edit": "WRITE",
    "write": "WRITE",
    "str_replace": "WRITE",
    "str_replace_editor": "WRITE",
    "bash": "SHELL",
    "powershell": "SHELL",
    "shell": "SHELL",
}


def read_stdin_json() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def debug_dump(payload: dict, event: str) -> None:
    if os.environ.get("COPILOT_EVALS_DEBUG") not in ("1", "true", "True"):
        return
    try:
        dbg = workspace_root() / "hook_debug.log"
        with open(dbg, "a", encoding="utf-8") as f:
            f.write(f"[{now_str()}] event={event} payload={json.dumps(payload)}\n")
    except OSError:
        pass


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def append_line(event_type: str, payload_text: str) -> None:
    line = f"[{now_str()}] {event_type} {payload_text}"
    try:
        with open(audit_log_path(), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"hook_log: could not write audit.log: {e}", file=sys.stderr)


def extract_from_args(tool_args: dict, keys: tuple[str, ...]) -> str | None:
    if not isinstance(tool_args, dict):
        return None
    for k in keys:
        if k in tool_args and isinstance(tool_args[k], str) and tool_args[k].strip():
            return tool_args[k].strip()
    return None


def heuristic_path(tool_args: dict) -> str | None:
    """Fallback: first string value that looks like a path."""
    if not isinstance(tool_args, dict):
        return None
    for v in tool_args.values():
        if isinstance(v, str) and ("/" in v or "\\" in v or "." in v.split()[-1:][0] if v.split() else False):
            return v.strip()
    return None


# ── Event handlers ──────────────────────────────────────────────────────────────

def handle_tool(payload: dict) -> None:
    tool = str(payload.get("toolName", "")).lower()
    args = payload.get("toolArgs", {}) or {}
    event_type = TOOL_EVENT_MAP.get(tool)

    if event_type is None:
        return  # ignore tools we don't audit (web_fetch, ask_user, task, ...)

    if event_type == "SHELL":
        cmd = extract_from_args(args, COMMAND_KEYS)
        if cmd:
            append_line("SHELL", cmd)
        return

    # READ / WRITE — need a file path
    path = extract_from_args(args, PATH_KEYS) or heuristic_path(args)
    if not path:
        return
    append_line(event_type, path)

    # Sub-detection: reading a prompt/instruction file is also a SKILL/STEERING signal
    norm = path.replace("\\", "/").lower()
    if norm.endswith(".prompt.md"):
        append_line("SKILL", path)
    elif (norm.endswith(".instructions.md")
          or norm.endswith("copilot-instructions.md")
          or "/.github/instructions/" in norm and norm.endswith(".md")):
        append_line("STEERING", path)


def handle_prompt(payload: dict) -> None:
    # userPromptSubmitted: detect an explicit /slash-command (prompt-file invocation)
    text = ""
    for k in ("prompt", "userPrompt", "text", "message", "input"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            text = v.strip()
            break
    if text.startswith("/"):
        name = text[1:].split()[0] if len(text) > 1 else ""
        if name:
            append_line("SKILL", name)


def parse_apply_to(md_text: str) -> list[str]:
    """Extract applyTo globs from an instruction file's frontmatter."""
    globs: list[str] = []
    in_fm = False
    for line in md_text.splitlines():
        s = line.strip()
        if s == "---":
            if in_fm:
                break
            in_fm = True
            continue
        if in_fm and s.lower().startswith("applyto:"):
            val = s.split(":", 1)[1].strip().strip('"').strip("'")
            globs = [g.strip().strip('"').strip("'") for g in val.split(",") if g.strip()]
            break
    return globs


def glob_has_match(root: Path, pattern: str) -> bool:
    """Does any workspace file match the glob pattern? (precise — Path.glob understands **)."""
    pattern = pattern.replace("\\", "/").lstrip("/")
    # An all-files applyTo ("**", "**/*", "*") means always-active.
    if pattern in ("**", "**/*", "*", "**/**"):
        return True
    try:
        for _ in root.glob(pattern):
            return True
    except (OSError, ValueError):
        pass
    return False


def steering_already_logged_today() -> bool:
    log = audit_log_path()
    if not log.exists():
        return False
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            if "STEERING" in line and today in line:
                return True
    except OSError:
        pass
    return False


def handle_session(payload: dict) -> None:
    """sessionStart: log instruction files that are active/available (deduped per day).

    Faithful analog of Kiro's log-steering.ps1: always-on instructions
    (copilot-instructions.md) are logged unconditionally; scoped instruction
    files are logged when their applyTo glob matches at least one workspace file.
    """
    if steering_already_logged_today():
        return

    root = workspace_root()

    always = root / ".github" / "copilot-instructions.md"
    if always.exists():
        append_line("STEERING", str(always))

    # Scan every markdown instruction file — both the `*.instructions.md`
    # convention and plain `*.md` files (e.g. migration-rules.md) that carry an
    # `applyTo:` frontmatter, which is how the Struts→Spring Boot agents ship.
    instr_dir = root / ".github" / "instructions"
    if instr_dir.is_dir():
        for f in sorted(instr_dir.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            globs = parse_apply_to(text)
            active = (not globs) or any(glob_has_match(root, g) for g in globs)
            if active:
                append_line("STEERING", str(f))


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a Copilot hook event to audit.log")
    parser.add_argument("--event", required=True, choices=["tool", "prompt", "session"],
                        help="Which hook fired: tool=postToolUse, prompt=userPromptSubmitted, session=sessionStart")
    args = parser.parse_args()

    payload = read_stdin_json()
    debug_dump(payload, args.event)

    if args.event == "tool":
        handle_tool(payload)
    elif args.event == "prompt":
        handle_prompt(payload)
    elif args.event == "session":
        handle_session(payload)

    # Hooks must exit 0 and emit nothing on stdout unless influencing the agent.
    sys.exit(0)


if __name__ == "__main__":
    main()
