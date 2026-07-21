# Copilot Skill Evals

An evaluation framework for **GitHub Copilot** agents, prompt files, and
instruction files in VS Code / the Copilot CLI. It verifies four things about an
agent run:

1. **Output** — did the agent produce a correct artifact? (LLM-graded)
2. **Process** — did it act in the right order and obey hard rules? (e.g. never write to a read-only dir)
3. **Context** — did it read the files it needed, avoid forbidden ones, and have the right instructions active?
4. **Triggering** — did the correct instruction file auto-apply for a task? (optional)

It is a port of the [Kiro Skill Evals](../../Evals_Kiro) framework to the Copilot
ecosystem. The four eval types and the `audit.log` contract are preserved 1:1;
the only differences are the driver (**Copilot CLI** instead of `kiro-cli`) and
that observability comes from **Copilot's own event hooks**.

## Table of contents

- [Concept mapping: Kiro → Copilot](#concept-mapping-kiro--copilot)
- [Architecture & data flow](#architecture--data-flow)
- [What happens at runtime](#what-happens-at-runtime)
- [Prerequisites & install](#prerequisites--install)
- [Implementation reference (every file)](#implementation-reference-every-file)
- [The `audit.log` contract](#the-auditlog-contract)
- [Eval file schema](#eval-file-schema)
- [How to run — end to end](#how-to-run--end-to-end)
- [Offline self-test (no CLI, no tokens)](#offline-self-test-no-cli-no-tokens)
- [Running inside VS Code](#running-inside-vs-code)
- [Troubleshooting](#troubleshooting)
- [Repository structure](#repository-structure)

---

## Concept mapping: Kiro → Copilot

| Kiro concept | Copilot / VS Code equivalent |
|---|---|
| `kiro-cli chat --no-interactive` | **Copilot CLI** — `copilot -p "<prompt>"` (non-interactive) |
| Skill (`.kiro/skills/<Name>/SKILL.md`) | **Prompt file** `.github/prompts/<name>.prompt.md` (`/name`), or a **custom agent** `.github/agents/<name>.agent.md` (`@name`) |
| Steering, `inclusion: always` | `.github/copilot-instructions.md` (always loaded) |
| Steering, `inclusion: fileMatch` | `.github/instructions/*.instructions.md` (with `applyTo:` glob) |
| Hooks (`.kiro/hooks/*.kiro.hook`) writing `audit.log` | **Copilot hooks** (`.github/hooks/*.json`) writing `audit.log` via `hook_log.py` |
| Skill activation (triggering) | **Instruction auto-apply** (did the right `.instructions.md` apply) |

Because the `audit.log` format is identical to Kiro's, `process_assert.py` and
`context_assert.py` are near-verbatim ports.

---

## Architecture & data flow

There are two phases. **Phase A** runs the agent and captures what it did.
**Phase B** grades the captured evidence. They are decoupled by the `audit.log`
file and the produced artifact — you can re-run Phase B as often as you like
without re-running the agent.

```
 PHASE A — capture (needs Copilot CLI or VS Code)
 ┌──────────────────────────────────────────────────────────────────────┐
 │  you: run the agent          Copilot fires lifecycle hooks             │
 │  (run_agent.py  OR           defined in .github/hooks/audit.json       │
 │   VS Code agent  OR          each hook runs:                           │
 │   copilot -p …)      ─────▶  python .github/copilot/hook_log.py …      │
 │                              (payload arrives on stdin)                │
 │                                        │                               │
 │  the agent also writes                 ▼                               │
 │  its artifact(s) ───────▶  [ artifact.md ]   [ audit.log ]  ◀── hooks  │
 └──────────────────────────────────────────────────────────────────────┘
                                   │              │
 PHASE B — grade (pure Python; no CLI except the judge)
                                   ▼              ▼
        judge_eval.py ──reads──▶ artifact    audit.log ◀──reads── process_assert.py
        (LLM judge, uses CLI)                          ◀──reads── context_assert.py

        trigger_eval.py ── runs its own copilot -p probes (separate from the run above)
```

Key point: **nothing in this framework observes the agent directly.** Copilot
calls `hook_log.py` for you because `.github/hooks/audit.json` is present in the
workspace. `hook_log.py` translates each hook payload into one `audit.log` line.
The grader scripts then read that plain-text log — they never talk to the agent.

---

## What happens at runtime

When you trigger an agent (say `@audit`) in a workspace that contains
`.github/hooks/audit.json` and `.github/copilot/hook_log.py`:

| # | Event | Copilot runs | `hook_log.py` writes |
|---|---|---|---|
| 1 | **sessionStart** (once) | `hook_log.py --event session` | one `STEERING <path>` per active instruction file (scans `.github/instructions/*.md` + `copilot-instructions.md`, deduped per day) |
| 2 | **userPromptSubmitted** | `hook_log.py --event prompt` | `SKILL <name>` **only if** the prompt starts with `/` (a prompt-file invocation). An `@agent` mention writes nothing here — that's expected. |
| 3 | **postToolUse** (per tool call, after it completes) | `hook_log.py --event tool` | `READ`/`WRITE`/`SHELL <payload>` depending on the tool |

The `matcher` in `audit.json` (`view\|create\|edit\|bash\|powershell\|grep\|glob`)
selects which tools fire step 3. Example log from an `@audit` run:

```
[2026-07-21 10:00:00] STEERING …/.github/instructions/migration-rules.md
[2026-07-21 10:00:00] STEERING …/.github/instructions/migration-playbook.md
[2026-07-21 10:00:03] READ struts-app/src/main/resources/struts.xml
[2026-07-21 10:00:04] READ struts-app/src/main/java/.../PersonAction.java
[2026-07-21 10:00:30] WRITE migrate-spring-boot/docs/MIGRATION-INVENTORY.md
```

Timestamps are the moment the hook fired (i.e. the moment the agent acted), so
log order = action order, which is what `order` assertions and `--since` rely on.

---

## Prerequisites & install

- **GitHub Copilot CLI** (`copilot`) on PATH, signed in with an active license —
  needed for Phase A and for the judge. Verify: `copilot --version`.
  Install: `npm install -g @github/copilot` (or `winget install GitHub.CopilotCLI`),
  then run `copilot` once to authenticate.
- **Python 3.10+** on PATH as `python` (or `python3`) — the hooks and graders use it.
  No third-party packages.

**Installing into a target workspace.** Copilot discovers everything from the
workspace root, so copy these into the repo you want to evaluate:

```
.github/hooks/audit.json          # the hook wiring
.github/copilot/*.py              # the tooling
.github/copilot/evals/<Name>/     # your eval definitions
```

The hooks use **workspace-relative** paths, so there is **no `setup.ps1` patch
step** (Kiro embedded absolute paths and needed one). Nothing else is required —
`audit.json` being present is what makes Copilot call `hook_log.py`.

---

## Implementation reference (every file)

### `.github/hooks/audit.json` — the hook wiring

Copilot-native hook config (`version: 1`). Registers three events, each running
`hook_log.py` with a different `--event`. Both a `bash` and a `powershell`
command are given so it works on any OS; Copilot picks the right one.

```jsonc
{
  "version": 1,
  "hooks": {
    "sessionStart":        [ { "type": "command", "bash": "python3 .github/copilot/hook_log.py --event session", "powershell": "python .github/copilot/hook_log.py --event session" } ],
    "userPromptSubmitted": [ { "type": "command", "bash": "…--event prompt",  "powershell": "…--event prompt"  } ],
    "postToolUse":         [ { "type": "command", "matcher": "view|create|edit|bash|powershell|grep|glob", "bash": "…--event tool", "powershell": "…--event tool" } ]
  }
}
```

`matcher` is a regex on the tool name (anchored `^(?:…)$`). Remove the matcher to
log every tool. `timeoutSec` bounds each hook.

### `hook_log.py` — hook target (stdin JSON → one `audit.log` line)

The only script Copilot calls; you never invoke it manually. Reads the hook
payload from **stdin** and appends to `audit.log`.

- **`--event session`** → `handle_session()`: scans `.github/instructions/*.md` and
  `copilot-instructions.md`, parses each file's `applyTo:` frontmatter, and writes
  a `STEERING` line for every instruction whose glob matches a workspace file
  (an `applyTo: "**"` always matches). Deduped per calendar day so repeated
  sessions don't spam the log.
- **`--event prompt`** → `handle_prompt()`: pulls the prompt text (keys `prompt` /
  `userPrompt` / `text` / `message` / `input`); if it starts with `/`, writes
  `SKILL <name>`.
- **`--event tool`** → `handle_tool()`: maps `toolName` via `TOOL_EVENT_MAP`
  (`view`/`grep`/`glob`→READ, `create`/`edit`→WRITE, `bash`/`powershell`→SHELL),
  extracts the path from `toolArgs` (tries `PATH_KEYS`, then a heuristic) or the
  command from `COMMAND_KEYS`, and appends the line. If a read/written file is a
  `.prompt.md` it also logs `SKILL`; a `.instructions.md` (or anything under
  `.github/instructions/`) also logs `STEERING`.
- **Log location:** `COPILOT_EVALS_AUDIT_LOG` env var if set, else
  `<workspace-root>/audit.log` (workspace root is derived from the script's own
  path, so it's correct regardless of the hook's cwd).
- **Calibration:** set `COPILOT_EVALS_DEBUG=1` to also append every raw payload to
  `hook_debug.log`. Tunable knobs are `PATH_KEYS`, `COMMAND_KEYS`, and
  `TOOL_EVENT_MAP` at the top of the file. Always exits 0.

### `run_agent.py` — drive the agent headlessly (Phase A)

Convenience wrapper that runs the agent so the hooks capture the run.

- Resolves the `copilot` binary, optionally truncates `audit.log` (`--reset-audit`),
  then runs `copilot -p <prompt> --allow-all-tools --allow-all-paths --no-ask-user [--model M]`
  with `cwd = --workspace`.
- Warns if `.github/hooks/audit.json` isn't in the workspace (hooks wouldn't fire).
- Prints how many event lines the run produced; exits with the CLI's return code.
- Args: `--prompt` / `--prompt-file` (one required), `--workspace`, `--audit`,
  `--reset-audit`, `--model`, `--timeout` (default 600s).
- You can skip this entirely and just run the agent in VS Code — the hooks fire
  the same way.

### `process_assert.py` — ordering / presence checks (Phase B)

Reads `audit.log`, evaluates `case.process_assertions`.

- Parses each `[ts] TYPE path` line into an event; `--since MINUTES` windows by time.
- Pattern form `"<EVENT> <glob>"`; `event_matches()` fnmatches the type and the
  normalized path (`\`→`/`).
- Assertion types: `order` (first match's index < then match's index), `present`
  (≥1 match), `absent` (0 matches).
- Prints `Score X/Y` + per-check `[PASS]`/`[FAIL]`; **exits 0 iff all pass**.
- Args: `--evals`, `--case`, `--log`, `--since`, `--out`, `--json`.

### `context_assert.py` — reads / steering / forbidden checks (Phase B)

Reads `audit.log`, evaluates `case.context_assertions`.

- Collects `READ` and `STEERING` paths; also mines `SHELL` command lines for
  read-like operations (`Get-Content`, `cat`, `type`, …) and counts those as reads.
- `matches_any()` does a full-path glob match, plus a filename-only fallback **only
  when the pattern has no `/`** (so a path glob like `*credentials/*` can't collapse
  to matching everything).
- Checks `required_reads` (≥1 match each), `required_steering` (≥1 match each),
  `forbidden_reads` (0 matches each). `Score X/Y`, **exits 0 iff all pass**.
- Args: `--evals`, `--case`, `--log`, `--since`, `--out`, `--json`.

### `judge_eval.py` — LLM output grading (Phase B, uses the CLI)

Grades a produced artifact against natural-language assertions.

- Builds a grader prompt from `case.assertions` + `case.knowledge_assertions` +
  the artifact text, asking for a strict JSON array `[{assertion, pass, reason}]`.
- Writes that prompt to a temp file and runs
  `copilot -p "Read <tmp> and follow it… return only the JSON array" -s --allow-all-tools --allow-all-paths --no-ask-user [--model M]`
  (temp-file indirection avoids the Windows command-length limit for big artifacts).
- Robustly extracts the JSON array from the model output; prints `Score X/Y`;
  **exits 0 iff all assertions pass**.
- Args: `--evals`, `--case`, `--artifact`, `--workspace`, `--model`, `--out`, `--save-prompt`.

### `trigger_eval.py` — instruction auto-apply (optional, uses the CLI)

Tests whether the right instruction file activates for a task.

- Reads `triggering.json`; for each prompt runs `copilot -p` and watches stdout for
  the instruction's **canary `signal`** token (fallback: the instruction filename).
  Detected = "instruction applied". `applied == should_trigger` → pass.
- Skip this whole eval for always-on instructions (`applyTo: "**"`) — auto-apply is
  trivial there.
- Args: `--triggering`, `--workspace`, `--timeout` (90s), `--model`, `--out`, `--filter`.

---

## The `audit.log` contract

Plain text, one event per line. `hook_log.py` writes it; the graders read it.

| Event | Meaning | Line format |
|---|---|---|
| `READ` | Agent read a file | `[YYYY-MM-DD HH:MM:SS] READ <path>` |
| `WRITE` | Agent wrote/edited a file | `[YYYY-MM-DD HH:MM:SS] WRITE <path>` |
| `SHELL` | Agent ran a shell command | `[YYYY-MM-DD HH:MM:SS] SHELL <command>` |
| `SKILL` | A prompt file (`/name`) was invoked | `[YYYY-MM-DD HH:MM:SS] SKILL <name>` |
| `STEERING` | An instruction file was active | `[YYYY-MM-DD HH:MM:SS] STEERING <path>` |

---

## Eval file schema

Keys prefixed with `_` (e.g. `_help`) are comments — the tooling ignores them.
Both files are plain JSON. Copy `.github/copilot/evals/_TEMPLATE/` to start.

### `evals.json` (required)

Top level `{ "evals": [ <case>, ... ] }`; other top-level keys are informational.
Each **case**:

| Field | Used by | Meaning |
|---|---|---|
| `id` | all | Integer case id (`--case`). |
| `name` | — | Human label. |
| `task` | you | The exact prompt you send the agent (record-keeping). |
| `assertions` | `judge_eval.py` | Natural-language claims about the artifact; each graded pass/fail. |
| `knowledge_assertions` | `judge_eval.py` | Optional `{claim, source, rationale}` — facts tied to real source, to ground the judge. |
| `process_assertions` | `process_assert.py` | Ordering/presence checks (below). |
| `context_assertions` | `context_assert.py` | Reads / steering / forbidden (below). |

**`process_assertions`** — each entry has a `type`:
- `{ "type": "present", "pattern": "<EVENT> <glob>", "description": "…" }` — ≥1 matching event.
- `{ "type": "absent",  "pattern": "<EVENT> <glob>", "description": "…" }` — 0 matching events (read-only rules, e.g. `WRITE *legacy-app/*`).
- `{ "type": "order", "first": "<EVENT> <glob>", "then": "<EVENT> <glob>", "description": "…" }` — first occurs before then.

`<EVENT>` ∈ `READ | WRITE | SHELL | SKILL | STEERING | *`.

**`context_assertions`** — three optional lists of `{ "pattern", "description" }`:
`required_reads` (must be read), `required_steering` (instruction must be active),
`forbidden_reads` (must not be read).

### `triggering.json` (optional)

`{ "instruction_name", "instruction_file", "signal", "prompts": [ {text, should_trigger, context_file?}, … ] }`.
Skip entirely for always-on instructions.

---

## How to run — end to end

All commands from the **workspace root** (the folder containing `.github/`).
Example uses a suite named `<Name>` with case `1`.

### Step 1 — run the agent (Phase A, captures `audit.log`)

```powershell
python .github\copilot\run_agent.py `
  --prompt "<your task — e.g. @audit Audit struts-app/ and produce the inventory>" `
  --workspace "." `
  --reset-audit `
  --model claude-sonnet-4.6
```

`--reset-audit` clears the log so it holds only this run. When it finishes,
`audit.log` exists and the agent's artifact has been written. (Equivalently, run
the task in the VS Code Copilot agent — the hooks capture it identically.)

### Step 2 — process assertions (reads `audit.log`; no tokens)

```powershell
python .github\copilot\process_assert.py --evals ".github\copilot\evals\<Name>\evals.json" --case 1 --log audit.log --out process_results.json
```

### Step 3 — context assertions (reads `audit.log`; no tokens)

```powershell
python .github\copilot\context_assert.py --evals ".github\copilot\evals\<Name>\evals.json" --case 1 --log audit.log --out context_results.json
```

### Step 4 — output judge (reads the artifact; uses the CLI → tokens)

Point `--artifact` at what the run actually produced. Run once per case that has
`assertions`:

```powershell
python .github\copilot\judge_eval.py --evals ".github\copilot\evals\<Name>\evals.json" --case 1 --artifact "<path\to\produced-doc.md>" --workspace "." --model claude-sonnet-4.6 --out judge_results.json
```

### Step 5 — instruction auto-apply (optional; uses the CLI)

```powershell
python .github\copilot\trigger_eval.py --triggering ".github\copilot\evals\<Name>\triggering.json" --workspace "." --timeout 90 --model claude-sonnet-4.6
```

### Reading the results

Every grader prints `Score X/Y (Z%)` and `[PASS]`/`[FAIL]` per check, and
**exits 0 if all passed, 1 otherwise** — so CI can gate on the exit code:

```powershell
python .github\copilot\process_assert.py --evals "…" --case 1 --log audit.log
echo $LASTEXITCODE      # 0 = all passed, 1 = at least one failed
```

`--out results.json` saves machine-readable results for any grader.

### Run everything in one go (bash)

```bash
E=".github/copilot/evals/<Name>/evals.json"
python .github/copilot/process_assert.py --evals "$E" --case 1 --log audit.log
python .github/copilot/context_assert.py --evals "$E" --case 1 --log audit.log
python .github/copilot/judge_eval.py     --evals "$E" --case 1 --artifact "<doc>.md" --workspace "." --model claude-sonnet-4.6
echo "combined exit via && above; any non-zero = a failure"
```

---

## Offline self-test (no CLI, no tokens)

You can validate the whole pipeline **without Copilot** by feeding `hook_log.py`
the same JSON the hooks would send, then running the graders. This is the fastest
way to confirm the framework and your `evals.json` patterns are wired correctly,
and it's what to put in CI for the framework itself.

```bash
export COPILOT_EVALS_AUDIT_LOG=./audit.log && rm -f audit.log
echo '{"sessionId":"t"}'                                                               | python .github/copilot/hook_log.py --event session
echo '{"toolName":"view","toolArgs":{"path":"struts-app/src/main/resources/struts.xml"}}' | python .github/copilot/hook_log.py --event tool
echo '{"toolName":"create","toolArgs":{"path":"migrate-spring-boot/docs/MIGRATION-INVENTORY.md"}}' | python .github/copilot/hook_log.py --event tool
python .github/copilot/process_assert.py --evals ".github/copilot/evals/<Name>/evals.json" --case 1 --log audit.log
python .github/copilot/context_assert.py --evals ".github/copilot/evals/<Name>/evals.json" --case 1 --log audit.log
```

**Always add a negative case** to prove the checks catch violations — e.g. inject
a forbidden write and confirm the `absent` assertion fails:

```bash
echo '{"toolName":"edit","toolArgs":{"path":"struts-app/pom.xml"}}' | python .github/copilot/hook_log.py --event tool
python .github/copilot/process_assert.py --evals ".github/copilot/evals/<Name>/evals.json" --case 1 --log audit.log
#  expect [FAIL] on the read-only rule, exit code 1
```

---

## Running inside VS Code

The same `.github/hooks/audit.json` is read by the VS Code Copilot agent, so you
don't need the CLI to capture a run:

1. Open the workspace (with `.github/hooks/` + `.github/copilot/` present) and run
   your task in the Copilot **agent**. The hooks write `audit.log` live.
2. Run `process_assert.py` / `context_assert.py` against that `audit.log`, and
   `judge_eval.py` against the produced artifact.

Only the CLI-driven pieces (`run_agent.py`, the `judge_eval.py` judge, and
`trigger_eval.py`) need `copilot`; the two log graders are pure Python.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `audit.log` is empty after a run | Hooks didn't fire — is `.github/hooks/audit.json` in the workspace root? Is `python` on PATH? |
| `READ`/`WRITE` lines have blank paths | The CLI's `toolArgs` uses a key `hook_log.py` doesn't know. Run with `COPILOT_EVALS_DEBUG=1`, inspect `hook_debug.log`, add the key to `PATH_KEYS` / `COMMAND_KEYS`. |
| `required_steering` fails | Your instruction files aren't `*.instructions.md` and aren't under `.github/instructions/`, or their `applyTo` glob matched no workspace file. Check the `STEERING` lines actually written. |
| Judge returns nothing / unparseable | The model didn't return clean JSON. Re-run with `--save-prompt` to inspect, and confirm `--model` is valid and you're signed in. |
| `copilot: command not found` | Install the CLI and authenticate (see [Prerequisites](#prerequisites--install)). The log graders still work offline. |
| Old entries pollute results | Use `--reset-audit` on the run, or `--since MINUTES` on the graders. |

---

## Repository structure

```
<workspace-root>/
  .github/
    copilot-instructions.md              # always-on instructions (optional)
    instructions/*.instructions.md       # scoped instructions (optional)
    prompts/*.prompt.md                  # prompt files (optional)
    agents/*.agent.md                    # custom agents (optional)
    hooks/
      audit.json                         # hook config — makes Copilot call hook_log.py
    copilot/                             # the eval tooling
      hook_log.py                        # hook target: stdin JSON -> audit.log line
      run_agent.py                       # drive the agent headlessly (Phase A)
      process_assert.py                  # ordering / present / absent (Phase B)
      context_assert.py                  # reads / steering / forbidden (Phase B)
      judge_eval.py                      # LLM output grading (Phase B)
      trigger_eval.py                    # instruction auto-apply (optional)
      evals/
        _TEMPLATE/                       # copy this per subject you test
          evals.json                     # REQUIRED
          triggering.json                # OPTIONAL
        <Name>/                          # your filled-in copy
          evals.json
          triggering.json
  audit.log                              # written live by hooks (not committed)
  hook_debug.log                         # only when COPILOT_EVALS_DEBUG=1 (not committed)
```

This directory ships **tooling + a `_TEMPLATE`** only — bring your own prompt /
instruction files and eval definitions.

**Live worked example:** the Struts→Spring Boot migration agents at
[`../../struts-to-spring-boot-migration-agent/`](../../struts-to-spring-boot-migration-agent/.github/copilot/README-EVALS.md)
have this framework installed against a real agent (`@audit`) and real source —
see its `.github/copilot/evals/Audit/evals.json` for a complete case.
