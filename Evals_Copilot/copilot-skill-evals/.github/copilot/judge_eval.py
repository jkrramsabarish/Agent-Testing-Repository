#!/usr/bin/env python3
"""Automated output assertion evaluator for Copilot CLI agent artifacts.

Copilot analog of Kiro's judge_eval.py. Generates a judge prompt from
evals.json + a generated artifact, feeds it to `copilot -p` as the judge model,
extracts the JSON grading response, and writes structured pass/fail results.

The judge prompt is written to a temp file and the model is asked to read it,
which sidesteps the Windows CreateProcess 32 767-character argument limit for
large artifacts (the same problem Kiro solved by piping via stdin).

Usage:
    python judge_eval.py --evals PATH --case ID --artifact PATH [--out PATH] [--workspace PATH] [--model NAME]

Example:
    python .github/copilot/judge_eval.py \
        --evals ".github/copilot/evals/<Name>/evals.json" \
        --case 1 \
        --artifact "migration/SPEC.md" \
        --out "judge_results.json" \
        --workspace "C:/path/to/workspace" \
        --model claude-sonnet-4.6
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def build_judge_prompt(case: dict, artifact_name: str, artifact_text: str) -> str:
    assertions = case.get("assertions", [])
    knowledge_assertions = case.get("knowledge_assertions", [])

    prompt = []
    prompt.append("You are an evaluation grader.")
    prompt.append("Determine whether the produced artifact satisfies the assertions.")
    prompt.append("Return ONLY a JSON array with objects containing:")
    prompt.append('- "assertion": the assertion text')
    prompt.append('- "pass": true or false')
    prompt.append('- "reason": one-sentence justification')
    prompt.append("Do not use any tools. Do not write files. Output only the JSON array.")
    prompt.append("")
    prompt.append(f"## Artifact: {artifact_name}")
    prompt.append(artifact_text.strip())
    prompt.append("")
    prompt.append("## Assertions to grade")

    for index, assertion in enumerate(assertions, 1):
        prompt.append(f"{index}. {assertion}")

    if knowledge_assertions:
        prompt.append("")
        prompt.append("## Knowledge assertions")
        for index, ka in enumerate(knowledge_assertions, 1):
            prompt.append(
                f'{index}. Claim: {ka["claim"]}\n'
                f'   Source: {ka["source"]}\n'
                f'   Rationale: {ka["rationale"]}'
            )

    return "\n".join(prompt)


def extract_json_array(text: str) -> list | None:
    """Extract the first JSON array found in a string (handles preamble/postamble)."""
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    pattern = r"\[\s*\{.*?\}\s*\]"
    matches = re.findall(pattern, text, re.DOTALL)
    for match in matches:
        try:
            result = json.loads(match)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            continue

    return None


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


def run_judge(judge_prompt: str, workspace: str, model: str | None) -> tuple[str, int]:
    """Run the judge via copilot -p, passing the prompt through a temp file.

    Large artifacts can exceed the Windows command-line length limit if passed
    as an argument, so we write the judge prompt to a temp file and instruct the
    model to read it. --allow-all-paths lets it read the temp file outside the
    workspace; --allow-all-tools permits the single read.
    """
    copilot = resolve_copilot_cli()

    with tempfile.NamedTemporaryFile("w", suffix=".judge.txt", delete=False, encoding="utf-8") as tf:
        tf.write(judge_prompt)
        prompt_file = tf.name

    directive = (
        f"Read the file at {prompt_file} and follow the grading instructions inside it "
        f"exactly. Do not modify any files. Return ONLY the JSON array it asks for."
    )
    cmd = [
        copilot, "-p", directive,
        "-s",                 # suppress stats/decoration — clean output for parsing
        "--allow-all-tools",
        "--allow-all-paths",
        "--no-ask-user",
    ]
    if model:
        cmd += ["--model", model]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=workspace,
            timeout=180,
        )
        return (result.stdout or "") + (result.stderr or ""), result.returncode
    except subprocess.TimeoutExpired:
        return "Error: copilot judge timed out after 180s", 1
    except FileNotFoundError:
        return f"Error: copilot CLI not found (tried: {copilot})", 1
    finally:
        try:
            Path(prompt_file).unlink()
        except OSError:
            pass


def print_results(results: list[dict], case_id: int) -> int:
    passed = sum(1 for r in results if r.get("pass"))
    total = len(results)
    score = passed / total if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  Output Assertions — Case {case_id}")
    print(f"  Score: {passed}/{total} ({score:.0%})")
    print(f"{'=' * 60}")

    for r in results:
        icon = "PASS" if r.get("pass") else "FAIL"
        print(f"\n  [{icon}] {r.get('assertion', '(unknown)')}")
        print(f"        -> {r.get('reason', '')}")

    print(f"\n{'=' * 60}\n")
    return 0 if passed == total else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run output assertion eval via copilot -p judge")
    parser.add_argument("--evals", required=True, help="Path to evals.json")
    parser.add_argument("--case", type=int, required=True, help="Eval case ID")
    parser.add_argument("--artifact", required=True, help="Path to the generated artifact (e.g. migration/SPEC.md)")
    parser.add_argument("--out", default=None, help="Path to write JSON results")
    parser.add_argument("--workspace", default=".", help="Workspace directory for copilot (default: current directory)")
    parser.add_argument("--model", default=None, help="Judge model (e.g. claude-sonnet-4.6, gpt-5.2)")
    parser.add_argument("--save-prompt", default=None, help="Optional path to save the generated judge prompt")
    args = parser.parse_args()

    evals_path = Path(args.evals)
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    case = next((c for c in data["evals"] if c["id"] == args.case), None)
    if not case:
        print(f"Error: case id {args.case} not found in {evals_path}")
        sys.exit(1)

    artifact_path = Path(args.artifact)
    if not artifact_path.exists():
        print(f"Error: artifact not found: {artifact_path}")
        sys.exit(1)
    artifact_text = artifact_path.read_text(encoding="utf-8")

    judge_prompt = build_judge_prompt(case, artifact_path.name, artifact_text)

    if args.save_prompt:
        Path(args.save_prompt).write_text(judge_prompt, encoding="utf-8")
        print(f"Judge prompt saved to: {args.save_prompt}")

    total_assertions = len(case.get("assertions", [])) + len(case.get("knowledge_assertions", []))
    workspace = str(Path(args.workspace).resolve())

    print(f"\nOutput Assertion Eval — Case {args.case}")
    print(f"Artifact:    {artifact_path}")
    print(f"Assertions:  {total_assertions}")
    print(f"Workspace:   {workspace}")
    print(f"Model:       {args.model or '(CLI default)'}")
    print(f"\nRunning judge via copilot -p ...")

    raw_output, exit_code = run_judge(judge_prompt, workspace, args.model)
    results = extract_json_array(raw_output)

    if results is None or len(results) == 0:
        print("\nError: could not extract JSON array from copilot output (empty or unparseable).")
        print("\n--- Raw output (first 3000 chars) ---")
        print(raw_output[:3000])
        sys.exit(1)

    final_exit = print_results(results, args.case)

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote results to: {args.out}")

    sys.exit(final_exit)


if __name__ == "__main__":
    main()
