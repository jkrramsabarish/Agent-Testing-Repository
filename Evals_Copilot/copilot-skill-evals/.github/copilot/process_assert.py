#!/usr/bin/env python3
"""Process assertion checker for Copilot prompt/instruction evals.

Reads audit.log chronologically (produced live by the hooks via hook_log.py)
and checks process_assertions defined in evals.json. The audit.log format is
identical to Kiro's, so this checker is a direct port.

Supports three assertion types:
  - order:   event matching 'first' pattern must appear before event matching 'then' pattern
  - present: at least one event matching 'pattern' must exist
  - absent:  no event matching 'pattern' must exist

Usage:
    python process_assert.py --evals PATH --case ID --log PATH [--since MINUTES] [--out PATH]

Example:
    python .github/copilot/process_assert.py \
        --evals ".github/copilot/evals/<Name>/evals.json" \
        --case 1 \
        --log audit.log \
        --out process_results.json
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ── Log parsing ───────────────────────────────────────────────────────────────

def parse_audit_log(log_path: Path, since: datetime | None = None) -> list[dict]:
    """Parse audit.log into a chronological list of events.

    Each event is: { 'ts': datetime, 'type': str, 'path': str, 'raw': str }
    Supported types: READ, WRITE, SHELL, SKILL, STEERING
    """
    events = []

    if not log_path.exists():
        return events

    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            ts_str = line[1:20]  # "YYYY-MM-DD HH:MM:SS"
            rest = line[22:].strip()
            event_type, _, path = rest.partition(" ")
            path = path.split(" (")[0].strip()
        except (IndexError, ValueError):
            continue

        if event_type not in ("READ", "WRITE", "SHELL", "SKILL", "STEERING"):
            continue

        try:
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            ts = None

        if since and ts and ts < since:
            continue

        events.append({
            "ts": ts,
            "type": event_type,
            "path": path,
            "raw": f"{event_type} {path}",
        })

    return events


# ── Pattern matching ──────────────────────────────────────────────────────────

def event_matches(event: dict, pattern: str) -> bool:
    """Check if an event matches a pattern like 'WRITE *SPEC.md' or 'READ */models/*.rb'.

    Pattern format: '<EVENT_TYPE> <path_glob>'
    EVENT_TYPE can be READ, WRITE, SHELL, SKILL, STEERING, or * for any.
    """
    parts = pattern.strip().split(" ", 1)
    if len(parts) == 1:
        type_pat = "*"
        path_pat = parts[0]
    else:
        type_pat, path_pat = parts[0], parts[1]

    if type_pat != "*" and not fnmatch.fnmatch(event["type"], type_pat):
        return False

    normalized_path = event["path"].replace("\\", "/")
    normalized_pattern = path_pat.replace("\\", "/")
    return fnmatch.fnmatch(normalized_path, normalized_pattern)


def find_first_matching(events: list[dict], pattern: str) -> dict | None:
    for event in events:
        if event_matches(event, pattern):
            return event
    return None


def find_all_matching(events: list[dict], pattern: str) -> list[dict]:
    return [e for e in events if event_matches(e, pattern)]


# ── Assertion checking ────────────────────────────────────────────────────────

def check_order(events: list[dict], assertion: dict) -> dict:
    first_pat = assertion["first"]
    then_pat = assertion["then"]
    description = assertion.get("description", f"'{first_pat}' before '{then_pat}'")

    first_event = find_first_matching(events, first_pat)
    then_event = find_first_matching(events, then_pat)

    if first_event is None and then_event is None:
        return {
            "type": "order", "description": description, "pass": False,
            "reason": f"Neither '{first_pat}' nor '{then_pat}' found in log",
            "first_match": None, "then_match": None,
        }

    if first_event is None:
        return {
            "type": "order", "description": description, "pass": False,
            "reason": f"No event matching '{first_pat}' found — cannot verify order",
            "first_match": None, "then_match": then_event["raw"],
        }

    if then_event is None:
        return {
            "type": "order", "description": description, "pass": False,
            "reason": f"No event matching '{then_pat}' found — expected action never happened",
            "first_match": first_event["raw"], "then_match": None,
        }

    first_idx = events.index(first_event)
    then_idx = events.index(then_event)
    passed = first_idx < then_idx

    return {
        "type": "order", "description": description, "pass": passed,
        "reason": (
            f"OK '{first_event['raw']}' (pos {first_idx}) before '{then_event['raw']}' (pos {then_idx})"
            if passed
            else f"'{then_event['raw']}' (pos {then_idx}) appeared BEFORE '{first_event['raw']}' (pos {first_idx})"
        ),
        "first_match": first_event["raw"], "then_match": then_event["raw"],
    }


def check_present(events: list[dict], assertion: dict) -> dict:
    pattern = assertion["pattern"]
    description = assertion.get("description", f"'{pattern}' must be present")

    matches = find_all_matching(events, pattern)
    passed = len(matches) > 0

    return {
        "type": "present", "description": description, "pass": passed,
        "reason": (
            f"Found {len(matches)} matching event(s): {[m['raw'] for m in matches[:3]]}"
            if passed
            else f"No events matching '{pattern}' found in log"
        ),
        "matched": [m["raw"] for m in matches],
    }


def check_absent(events: list[dict], assertion: dict) -> dict:
    pattern = assertion["pattern"]
    description = assertion.get("description", f"'{pattern}' must be absent")

    matches = find_all_matching(events, pattern)
    passed = len(matches) == 0

    return {
        "type": "absent", "description": description, "pass": passed,
        "reason": (
            "No forbidden events found — OK"
            if passed
            else f"Forbidden event(s) found: {[m['raw'] for m in matches]}"
        ),
        "matched": [m["raw"] for m in matches],
    }


def check_process_assertions(process_assertions: list[dict], events: list[dict]) -> list[dict]:
    results = []
    for assertion in process_assertions:
        atype = assertion.get("type")
        if atype == "order":
            results.append(check_order(events, assertion))
        elif atype == "present":
            results.append(check_present(events, assertion))
        elif atype == "absent":
            results.append(check_absent(events, assertion))
        else:
            results.append({
                "type": atype,
                "description": assertion.get("description", "unknown"),
                "pass": False,
                "reason": f"Unknown assertion type: '{atype}'",
            })
    return results


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_results(results: list[dict], case_id: int, event_count: int) -> int:
    passed = sum(1 for r in results if r["pass"])
    total = len(results)
    score = passed / total if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  Process Assertions — Case {case_id}")
    print(f"  Events in window: {event_count}")
    print(f"  Score: {passed}/{total} ({score:.0%})")
    print(f"{'=' * 60}")

    for r in results:
        icon = "PASS" if r["pass"] else "FAIL"
        type_label = r["type"].upper()
        print(f"\n  [{icon}] {type_label}: {r['description']}")
        print(f"        -> {r['reason']}")

    print(f"\n{'=' * 60}\n")
    return 0 if passed == total else 1


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Check process assertions from audit.log against evals.json")
    parser.add_argument("--evals", required=True, help="Path to evals.json")
    parser.add_argument("--case", type=int, required=True, help="Eval case ID to check")
    parser.add_argument("--log", required=True, help="Path to audit.log")
    parser.add_argument("--since", type=int, default=None, help="Only consider log entries from the last N minutes")
    parser.add_argument("--out", default=None, help="Optional path to write JSON results")
    parser.add_argument("--json", dest="json_out", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    evals_path = Path(args.evals)
    data = json.loads(evals_path.read_text(encoding="utf-8"))
    case = next((c for c in data["evals"] if c["id"] == args.case), None)
    if not case:
        print(f"Error: case id {args.case} not found in {evals_path}")
        sys.exit(1)

    process_assertions = case.get("process_assertions")
    if not process_assertions:
        print(f"No process_assertions defined for case {args.case}")
        sys.exit(0)

    since = None
    if args.since:
        since = datetime.now(timezone.utc) - timedelta(minutes=args.since)

    log_path = Path(args.log)
    events = parse_audit_log(log_path, since=since)

    print(f"\n  Audit window: {'last ' + str(args.since) + ' minutes' if args.since else 'all entries'}")
    print(f"  Events found: {len(events)}")

    if events:
        types = {}
        for e in events:
            types[e["type"]] = types.get(e["type"], 0) + 1
        for t, count in sorted(types.items()):
            print(f"    {t}: {count}")

    results = check_process_assertions(process_assertions, events)

    if args.json_out:
        output = json.dumps(results, indent=2)
        if args.out:
            Path(args.out).write_text(output, encoding="utf-8")
            print(f"Wrote JSON results to: {args.out}")
        else:
            print(output)
        sys.exit(0 if all(r["pass"] for r in results) else 1)

    exit_code = print_results(results, args.case, len(events))

    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote results to: {args.out}")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
