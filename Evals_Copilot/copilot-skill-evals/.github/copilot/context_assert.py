#!/usr/bin/env python3
"""Context assertion checker for Copilot prompt/instruction evals.

Reads audit.log (produced live by the hooks via hook_log.py), filters READ / STEERING
entries within a time window, and checks them against context_assertions defined
in evals.json. Direct port of Kiro's context_assert.py — the audit.log contract
is identical.

  - required_reads:    files the agent MUST have read
  - required_steering: instruction files that MUST have been active
  - forbidden_reads:   files the agent must NOT have read

Usage:
    python context_assert.py --evals PATH --case ID --log PATH [--since MINUTES]

Example:
    python .github/copilot/context_assert.py \
        --evals ".github/copilot/evals/<Name>/evals.json" \
        --case 1 \
        --log audit.log
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ── Log parsing ──────────────────────────────────────────────────────────────

# Patterns that indicate a file is being READ inside a SHELL command entry.
SHELL_READ_PATTERNS = [
    r'Get-Content\s+(?:-Path\s+)?["\']?([A-Za-z]:[^\s"\'|;]+|[^\s"\'|;]+\.\w+)["\']?',
    r'\bgc\b\s+["\']?([A-Za-z]:[^\s"\'|;]+|[^\s"\'|;]+\.\w+)["\']?',
    r'\bcat\b\s+["\']?([A-Za-z]:[^\s"\'|;]+|[^\s"\'|;]+\.\w+)["\']?',
    r'\btype\b\s+["\']?([A-Za-z]:[^\s"\'|;]+|[^\s"\'|;]+\.\w+)["\']?',
]


def extract_paths_from_shell_command(command: str) -> list[str]:
    """Extract file paths being read from a shell command string."""
    paths = []
    for pattern in SHELL_READ_PATTERNS:
        for match in re.finditer(pattern, command, re.IGNORECASE):
            path = match.group(1).strip().strip('"\'')
            if any(path.endswith(ext) for ext in [
                ".rb", ".py", ".java", ".md", ".json", ".yml", ".yaml",
                ".xml", ".txt", ".log", ".sql", ".sh", ".ps1", ".erb",
                ".html", ".js", ".ts", ".css", ".env", ".lock", ".toml",
                ".ru", ".gemspec", ".rake"
            ]) or ("." in path.split("/")[-1] and "\\" in path or "/" in path):
                paths.append(path)
    return list(set(paths))


def parse_audit_log(log_path: Path, since: datetime | None = None) -> dict[str, list[str]]:
    """Return {'READ': [...paths], 'STEERING': [...paths]} from audit.log."""
    entries: dict[str, list[str]] = {"READ": [], "STEERING": []}

    if not log_path.exists():
        return entries

    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            ts_part = line[1:20]
            rest = line[22:].strip()
            event_type, _, path_and_meta = rest.partition(" ")
            file_path = path_and_meta.split(" (")[0].strip()
        except (IndexError, ValueError):
            continue

        if since:
            try:
                ts = datetime.strptime(ts_part, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if ts < since:
                    continue
            except ValueError:
                pass

        if event_type in ("READ", "STEERING"):
            entries[event_type].append(file_path)
        elif event_type == "SHELL":
            shell_reads = extract_paths_from_shell_command(path_and_meta)
            entries["READ"].extend(shell_reads)

    entries["READ"] = list(dict.fromkeys(entries["READ"]))
    entries["STEERING"] = list(dict.fromkeys(entries["STEERING"]))
    return entries


# ── Pattern matching ─────────────────────────────────────────────────────────

def matches_any(path: str, patterns: list[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatch(normalized, normalized_pattern):
            return True
        # Filename-only fallback (so a bare pattern like "schema.rb" matches
        # "db/schema.rb"). Only when the pattern itself has NO path separator —
        # otherwise a path pattern like "*config/credentials/*" would reduce to
        # filename "*" and match every file, producing false forbidden_read hits.
        if "/" not in normalized_pattern:
            filename = normalized.split("/")[-1]
            if fnmatch.fnmatch(filename, normalized_pattern):
                return True
    return False


# ── Assertion checking ────────────────────────────────────────────────────────

def check_context_assertions(context_assertions: dict, reads: list[str], steerings: list[str]) -> list[dict]:
    results = []

    for req in context_assertions.get("required_reads", []):
        pattern = req["pattern"]
        matched = [r for r in reads if matches_any(r, [pattern])]
        passed = len(matched) > 0
        results.append({
            "type": "required_read", "pattern": pattern,
            "description": req.get("description", ""), "pass": passed, "matched": matched,
            "reason": (f"Found {len(matched)} matching file(s): {matched[:3]}" if passed
                       else f"No files matching '{pattern}' were read"),
        })

    for req in context_assertions.get("required_steering", []):
        pattern = req["pattern"]
        matched = [s for s in steerings if matches_any(s, [pattern])]
        passed = len(matched) > 0
        results.append({
            "type": "required_steering", "pattern": pattern,
            "description": req.get("description", ""), "pass": passed, "matched": matched,
            "reason": (f"Instruction file matched: {matched[0]}" if passed
                       else f"Required instruction '{pattern}' was not active"),
        })

    for req in context_assertions.get("forbidden_reads", []):
        pattern = req["pattern"]
        matched = [r for r in reads if matches_any(r, [pattern])]
        passed = len(matched) == 0
        results.append({
            "type": "forbidden_read", "pattern": pattern,
            "description": req.get("description", ""), "pass": passed, "matched": matched,
            "reason": ("No forbidden files were read — OK" if passed
                       else f"Forbidden file(s) were read: {matched}"),
        })

    return results


# ── Reporting ─────────────────────────────────────────────────────────────────

def format_results(results: list[dict], case_id: int) -> tuple[str, int]:
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    score = passed / total if total > 0 else 0

    lines = []
    lines.append(f"\n{'=' * 60}")
    lines.append(f"  Context Assertions — Case {case_id}")
    lines.append(f"  Score: {passed}/{total} ({score:.0%})")
    lines.append(f"{'=' * 60}")

    for r in results:
        icon = "PASS" if r["pass"] else "FAIL"
        type_label = {
            "required_read": "REQUIRED READ",
            "required_steering": "REQUIRED INSTRUCTION",
            "forbidden_read": "FORBIDDEN READ",
        }.get(r["type"], r["type"].upper())

        lines.append(f"\n  [{icon}] {type_label}: {r['pattern']}")
        lines.append(f"        {r['description']}")
        lines.append(f"        -> {r['reason']}")

    lines.append(f"\n{'=' * 60}\n")
    return "\n".join(lines), (0 if passed == total else 1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Check context assertions from audit.log against evals.json")
    parser.add_argument("--evals", required=True, help="Path to evals.json")
    parser.add_argument("--case", type=int, required=True, help="Eval case ID to check")
    parser.add_argument("--log", required=True, help="Path to audit.log")
    parser.add_argument("--since", type=int, default=None, help="Only consider log entries from the last N minutes")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Output results as JSON")
    parser.add_argument("--out", default=None, help="Optional path to write the output (text or JSON)")
    args = parser.parse_args()

    evals_path = Path(args.evals)
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    case = next((c for c in data["evals"] if c["id"] == args.case), None)
    if not case:
        print(f"Error: case id {args.case} not found in {evals_path}")
        sys.exit(1)

    context_assertions = case.get("context_assertions")
    if not context_assertions:
        print(f"No context_assertions defined for case {args.case}")
        sys.exit(0)

    since = None
    if args.since:
        since = datetime.now(timezone.utc) - timedelta(minutes=args.since)

    log_path = Path(args.log)
    entries = parse_audit_log(log_path, since=since)

    reads = entries["READ"]
    steerings = entries["STEERING"]

    print(f"\n  Audit window: {'last ' + str(args.since) + ' minutes' if args.since else 'all entries'}")
    print(f"  READ entries found:     {len(reads)}")
    print(f"  STEERING entries found: {len(steerings)}")

    results = check_context_assertions(context_assertions, reads, steerings)

    if args.json_out:
        output = json.dumps(results, indent=2)
        if args.out:
            Path(args.out).write_text(output, encoding="utf-8")
            print(f"Wrote JSON results to: {args.out}")
        else:
            print(output)
        sys.exit(0 if all(r["pass"] for r in results) else 1)

    text, exit_code = format_results(results, args.case)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Wrote results to: {args.out}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
