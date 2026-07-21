#!/usr/bin/env python3
"""Run a Copilot CLI agent task headlessly and produce the eval inputs.

This is the Copilot analog of "run the task in Kiro with hooks active". Copilot's
lifecycle hooks (configured in .github/hooks/audit.json) fire automatically while
the agent works and write audit.log live via hook_log.py — exactly like Kiro.
This helper just:

  1. (optionally) resets audit.log so the run is isolated,
  2. runs `copilot -p "<task prompt>"` in the workspace (hooks write audit.log).

The result — a generated artifact (written by the agent) plus audit.log — is
exactly what judge_eval.py / process_assert.py / context_assert.py expect.

Usage:
    python run_agent.py \
        --prompt "<your task prompt — invoke your prompt file or @agent>" \
        --workspace "C:/path/to/workspace" \
        --reset-audit \
        --model claude-sonnet-4.6
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def resolve_copilot_cli() -> str:
    for name in ("copilot", "copilot.exe"):
        found = shutil.which(name)
        if found:
            return found
    candidates = [
        Path.home() / "AppData" / "Local" / "Programs" / "copilot" / "copilot.exe",
        Path.home() / ".copilot" / "bin" / "copilot",
        Path("/usr/local/bin/copilot"),
        Path("/opt/homebrew/bin/copilot"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "copilot"


def run_agent(prompt: str, workspace: str, model: str | None, timeout: int) -> tuple[str, int]:
    copilot = resolve_copilot_cli()
    cmd = [
        copilot,
        "-p", prompt,
        "--allow-all-tools",   # agent needs read/write/shell to do the task
        "--allow-all-paths",
        "--no-ask-user",       # non-interactive: never pause for input
    ]
    if model:
        cmd += ["--model", model]

    print(f"Running: copilot -p <prompt> {'--model ' + model if model else ''}")
    print(f"Workspace: {workspace}")
    print("Hooks (.github/hooks/audit.json) will write audit.log live.\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            timeout=timeout,
        )
        return (result.stdout or "") + (result.stderr or ""), result.returncode
    except subprocess.TimeoutExpired:
        return f"Error: copilot timed out after {timeout}s", 1
    except FileNotFoundError:
        return f"Error: copilot CLI not found (tried: {copilot})", 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Copilot CLI agent task; hooks write audit.log live")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prompt", help="Task prompt to send to the agent")
    group.add_argument("--prompt-file", help="Read the task prompt from this file")
    parser.add_argument("--workspace", default=".", help="Workspace directory the agent runs in (must contain .github/hooks/)")
    parser.add_argument("--audit", default="audit.log", help="Path to the audit.log hooks write to (default: audit.log)")
    parser.add_argument("--reset-audit", action="store_true", help="Truncate audit.log before the run so it captures only this run")
    parser.add_argument("--model", default=None, help="Model to use (e.g. claude-sonnet-4.6, gpt-5.2)")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds before the agent run is aborted (default: 600)")
    args = parser.parse_args()

    prompt = args.prompt if args.prompt else Path(args.prompt_file).read_text(encoding="utf-8")
    workspace = Path(args.workspace).resolve()

    hooks_file = workspace / ".github" / "hooks" / "audit.json"
    if not hooks_file.exists():
        print(f"[warn] {hooks_file} not found — hooks will not fire and audit.log "
              f"will be empty. Copy .github/hooks/ and .github/copilot/ into the workspace.")

    audit_path = (workspace / args.audit) if not Path(args.audit).is_absolute() else Path(args.audit)
    if args.reset_audit:
        audit_path.write_text("", encoding="utf-8")
        print(f"Reset audit log: {audit_path}")

    _, code = run_agent(prompt, str(workspace), args.model, args.timeout)
    print("\n--- Agent run finished (exit code %d) ---" % code)

    n = 0
    if audit_path.exists():
        n = len([ln for ln in audit_path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()])
    print(f"audit.log now has {n} event line(s): {audit_path}")

    sys.exit(code)


if __name__ == "__main__":
    main()
