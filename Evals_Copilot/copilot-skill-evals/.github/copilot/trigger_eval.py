#!/usr/bin/env python3
"""Instruction auto-apply eval for Copilot instruction files.

Copilot analog of Kiro's trigger_eval.py. Kiro tests whether a natural-language
prompt causes the right *skill* to auto-activate. Copilot instruction files
(`.github/instructions/*.instructions.md`) instead auto-apply based on their
`applyTo` glob and semantic matching of their description to the task. This eval
tests that reinterpreted question:

    "For this task (optionally on this file), did the correct instruction file
     get applied — and does it correctly NOT apply for off-target tasks?"

DETECTION — the canary-signal method
    The agent doesn't reliably announce "instruction X was applied", so we make
    application observable. Each instruction file under test embeds a unique
    canary directive, e.g.:

        When these instructions are in effect, begin your reply with the exact
        token [[MY-INSTR-ACTIVE]] on its own line.

    This eval runs `copilot -p "<prompt>"` per case and checks whether that
    token appears in the output. Token present  => instruction applied.
    A `context_file` can be given per case so an `applyTo` glob actually fires
    (the file is named in the prompt so the agent works on it).

    Fallback: if no `signal` is configured, the instruction file's path
    appearing in the agent's stdout output is treated as "applied".

triggering.json schema:
    {
      "instruction_name": "my-instructions",
      "instruction_file": ".github/instructions/my-instructions.instructions.md",
      "signal": "[[MY-INSTR-ACTIVE]]",
      "prompts": [
        {"text": "<a task that SHOULD apply this instruction>",
         "should_trigger": true,  "context_file": "<a file matching its applyTo glob>"},
        {"text": "<an off-target task that should NOT apply it>",
         "should_trigger": false}
      ]
    }

Usage:
    python trigger_eval.py --triggering PATH --workspace PATH [--timeout SECONDS] [--model NAME] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
from datetime import datetime
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


def build_prompt(case: dict) -> str:
    """Compose the prompt, naming the context file so an applyTo glob can fire."""
    text = case["text"]
    ctx = case.get("context_file")
    if ctx:
        text = f"{text}\n\n(Work on the file: {ctx})"
    return text


def run_prompt(
    prompt: str,
    signal: str | None,
    instruction_file: str,
    workspace: str,
    timeout: int,
    model: str | None,
) -> tuple[bool, str, str]:
    """Run copilot -p for a single prompt; detect whether the instruction applied.

    Returns (applied, reason, captured_output).
    """
    collected: list[str] = []
    applied = False
    termination_reason = "completed"
    copilot = resolve_copilot_cli()

    # The signal (canary token) is the primary detector; the instruction file
    # basename in the agent's stdout is the fallback detector.
    signal_norm = signal if signal else None
    instr_signal = Path(instruction_file).name if instruction_file else None

    cmd = [copilot, "-p", prompt, "-s", "--allow-all-tools", "--allow-all-paths", "--no-ask-user"]
    if model:
        cmd += ["--model", model]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
        )
    except FileNotFoundError:
        return False, f"copilot CLI not found (tried: {copilot})", ""

    def stream_output() -> None:
        nonlocal applied, termination_reason
        try:
            for line in proc.stdout:
                collected.append(line)
                if signal_norm and signal_norm in line:
                    applied = True
                    termination_reason = "signal detected"
                    proc.kill()
                    break
                if not signal_norm and instr_signal and instr_signal in line.replace("\\", "/"):
                    applied = True
                    termination_reason = "instruction file referenced"
                    proc.kill()
                    break
        except ValueError:
            pass  # pipe closed

    reader = threading.Thread(target=stream_output, daemon=True)
    reader.start()
    reader.join(timeout=timeout)

    if reader.is_alive():
        proc.kill()
        reader.join(timeout=5)
        termination_reason = f"timeout after {timeout}s"

    captured = "".join(collected)

    # If the process finished without early-kill, do a final scan of the output.
    if not applied:
        if signal_norm and signal_norm in captured:
            applied = True
            termination_reason = "signal detected (post-scan)"
        elif not signal_norm and instr_signal and instr_signal in captured.replace("\\", "/"):
            applied = True
            termination_reason = "instruction file referenced (post-scan)"

    return applied, termination_reason, captured


def evaluate_case(case: dict, signal: str | None, instruction_file: str,
                  workspace: str, timeout: int, model: str | None,
                  index: int, total: int) -> dict:
    should_trigger = case["should_trigger"]
    prompt = build_prompt(case)

    print(f"\n[{index}/{total}] {'SHOULD' if should_trigger else 'SHOULD NOT'} apply")
    print(f"  Prompt: {case['text'][:80]}{'...' if len(case['text']) > 80 else ''}")
    if case.get("context_file"):
        print(f"  Context file: {case['context_file']}")

    applied, reason, _ = run_prompt(prompt, signal, instruction_file, workspace, timeout, model)

    passed = applied == should_trigger
    icon = "PASS" if passed else "FAIL"

    if passed:
        result_msg = (f"Instruction applied as expected ({reason})" if should_trigger
                      else f"Instruction correctly did not apply ({reason})")
    else:
        result_msg = (f"Instruction did NOT apply — expected it to ({reason})" if should_trigger
                      else f"Instruction applied — expected it NOT to ({reason})")

    print(f"  [{icon}] {result_msg}")

    return {
        "prompt": case["text"],
        "context_file": case.get("context_file"),
        "should_trigger": should_trigger,
        "applied": applied,
        "pass": passed,
        "reason": result_msg,
        "termination_reason": reason,
    }


def print_summary(results: list[dict], instruction_name: str) -> int:
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    score = passed / total if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  Instruction Auto-Apply Eval — {instruction_name}")
    print(f"  Score: {passed}/{total} ({score:.0%})")
    print(f"{'=' * 60}")

    failures = [r for r in results if not r["pass"]]
    if failures:
        print(f"\n  Failures:")
        for r in failures:
            print(f"    FAIL [{'APPLY' if r['should_trigger'] else 'NO-APPLY'}] {r['prompt'][:70]}")
            print(f"      -> {r['reason']}")

    print(f"\n{'=' * 60}\n")
    return 0 if passed == total else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run instruction auto-apply evals for a Copilot instruction file")
    parser.add_argument("--triggering", required=True, help="Path to triggering.json")
    parser.add_argument("--workspace", default=".", help="Workspace directory to run copilot from")
    parser.add_argument("--timeout", type=int, default=90, help="Seconds per prompt before declaring no-apply (default: 90)")
    parser.add_argument("--model", default=None, help="Model to use (e.g. claude-sonnet-4.6, gpt-5.2)")
    parser.add_argument("--out", default=None, help="Optional path to write JSON results")
    parser.add_argument("--filter", choices=["all", "positive", "negative"], default="all",
                        help="Run only positive (should_trigger=true), negative, or all cases")
    args = parser.parse_args()

    triggering_path = Path(args.triggering)
    if not triggering_path.exists():
        print(f"Error: {triggering_path} not found")
        sys.exit(1)

    data = json.loads(triggering_path.read_text(encoding="utf-8"))
    instruction_name = data.get("instruction_name", "Unknown Instruction")
    instruction_file = data.get("instruction_file", "")
    signal = data.get("signal")
    all_prompts = data.get("prompts", [])

    if args.filter == "positive":
        prompts = [p for p in all_prompts if p["should_trigger"]]
    elif args.filter == "negative":
        prompts = [p for p in all_prompts if not p["should_trigger"]]
    else:
        prompts = all_prompts

    if not prompts:
        print("No prompts found after filtering.")
        sys.exit(0)

    workspace = str(Path(args.workspace).resolve())

    print(f"\nInstruction Auto-Apply Eval: {instruction_name}")
    print(f"Instruction file: {instruction_file}")
    print(f"Detection:        {'canary signal ' + repr(signal) if signal else 'instruction-file reference (fallback)'}")
    print(f"Workspace:        {workspace}")
    print(f"Timeout:          {args.timeout}s per prompt")
    print(f"Model:            {args.model or '(CLI default)'}")
    print(f"Cases:            {len(prompts)} ({args.filter})")
    print(f"Started:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []
    for i, case in enumerate(prompts, 1):
        results.append(evaluate_case(
            case=case, signal=signal, instruction_file=instruction_file,
            workspace=workspace, timeout=args.timeout, model=args.model,
            index=i, total=len(prompts),
        ))

    exit_code = print_summary(results, instruction_name)

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote results to: {args.out}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
