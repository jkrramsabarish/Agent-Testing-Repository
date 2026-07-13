# Struts to Spring Boot — Migration Agents

> **Version:** 1.2 | **Playbook Source:** Struts to Spring Boot Migration Playbook v1.0, June 2025
> **Pattern:** Strangler Fig — one module at a time, rollback available at every stage

This repository is a self-contained workspace. Your Struts project, the generated Spring Boot project, and all migration documents all live here together. The `.github/agents/` directory holds the agent definitions that read from `struts-app/` and write to `spring-boot-app/`.

**Don't invoke the nine specialist agents by hand.** Invoke `@orchestrator` — it sequences all of them in the correct phase order, enforces every phase gate and absolute rule from `migration-rules.md`, and pauses for your explicit approval at each human-in-the-loop checkpoint. The per-agent invocation examples below still work (useful for re-running a single step or debugging), but the orchestrator is the intended entry point for driving the migration end to end.

---

## Repository Layout

```
struts-to-spring-boot-migration-agent/
│
├── .github/
│   ├── agents/                        ← 10 Custom Agent definitions
│   │   ├── orchestrator.agent.md      ← Drives all phases end-to-end, enforces gates, owns HITL checkpoints
│   │   ├── audit.agent.md             ← Phase 1: Read-only Struts inventory
│   │   ├── planner.agent.md           ← Phase 1: Migration order & risk plan
│   │   ├── project-bootstrap.agent.md ← Phase 2: Spring Boot project creation
│   │   ├── route-configuration.agent.md ← Phase 3: Security, interceptors, config
│   │   ├── code-transformation.agent.md ← Phase 4: Action → Controller migration
│   │   ├── view-migration.agent.md    ← Phase 5: JSP → Thymeleaf / REST
│   │   ├── quality-review.agent.md    ← Phase 4–5: Code review gate
│   │   ├── validation-testing.agent.md ← Phase 4–5: Test generation & execution
│   │   └── documentation.agent.md     ← All phases: Documentation production
│   ├── instructions/                  ← 6 shared instruction files (all agents reference these)
│   │   ├── migration-playbook.md      ← Phases 1–6, mapping tables, pitfalls
│   │   ├── migration-rules.md         ← 7 absolute rules + phase gates
│   │   ├── springboot-standards.md    ← Spring Boot patterns, project structure
│   │   ├── coding-guidelines.md       ← Java coding standards, forbidden patterns
│   │   ├── testing-guidelines.md      ← Test pyramid, coverage requirements
│   │   └── documentation-guidelines.md ← Document formats and writing standards
│   └── README.md                      ← this file
│
├── struts-app/                        ← PUT YOUR STRUTS PROJECT HERE (agents read, never write)
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/                  ← Action, Service, DAO, model classes
│   │   │   ├── resources/             ← struts.xml, hibernate configs, properties
│   │   │   └── webapp/                ← WEB-INF/web.xml, JSP views, static assets
│   │   └── test/
│   └── pom.xml
│
├── spring-boot-app/                   ← GENERATED SPRING BOOT PROJECT (agents write here)
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/.../
│   │   │   │   ├── config/            ← SecurityConfig, WebConfig
│   │   │   │   ├── controller/        ← Migrated controllers
│   │   │   │   ├── service/           ← Migrated services
│   │   │   │   ├── repository/        ← Spring Data JPA repositories
│   │   │   │   ├── model/ or entity/  ← Domain model / JPA entities
│   │   │   │   ├── dto/               ← Request / Response DTOs
│   │   │   │   ├── exception/         ← GlobalExceptionHandler + custom exceptions
│   │   │   │   └── filter/            ← OncePerRequestFilter implementations
│   │   │   └── resources/
│   │   │       ├── application.properties
│   │   │       ├── static/            ← CSS, JS, images (migrated from struts-app)
│   │   │       └── templates/         ← Thymeleaf HTML templates
│   │   └── test/java/.../
│   │       ├── controller/            ← @SpringBootTest + MockMvc tests
│   │       ├── service/               ← Unit tests with Mockito
│   │       ├── model/                 ← Value object tests
│   │       └── integration/           ← Full integration tests
│   └── pom.xml
│
└── docs/                              ← ALL MIGRATION DOCUMENTS LAND HERE
    ├── MIGRATION-INVENTORY.md         ← Audit Agent output, updated every phase
    ├── MIGRATION-PLAN.md              ← Planner Agent output
    ├── AUDIT-REPORT.md                ← Audit Agent summary
    ├── API-MAPPING.md                 ← URL mapping changes
    ├── ARCHITECTURE-REPORT.md         ← System architecture (post-migration)
    ├── ROLLBACK-GUIDE.md              ← Ops runbook for reverting traffic
    ├── RELEASE-NOTES.md               ← Cutover release notes
    └── modules/                       ← Per-module sign-off documents
        ├── MODULE-COMPLETION-REPORT.md
        ├── QUALITY-REPORT-{Module}.md
        └── VALIDATION-TESTING-REPORT.md
```

---

## Setup — Before You Start

**Step 1 — Drop your Struts project in:**
```bash
# Copy (or clone) your existing Struts WAR project into struts-app/
cp -r /path/to/your/legacy-struts-project/* struts-to-spring-boot-migration-agent/struts-app/
```
The `struts-app/` folder must contain your real Struts source code — `struts.xml`, Action classes, JSP files, `pom.xml`. No agents will modify anything inside it.

**Step 2 — Open in your IDE:**
```bash
code struts-to-spring-boot-migration-agent/
```
Open the single root folder so the agents can see the entire workspace including `struts-app/` and `spring-boot-app/`.

**Step 3 — Let the orchestrator drive the migration:**
```
@orchestrator
Begin the migration for struts-app/. Follow the phase gates in migration-rules.md
and pause for my approval at each checkpoint.
```
The orchestrator invokes audit, planner, project-bootstrap, route-configuration, and the per-module loop (code-transformation → view-migration → quality-review → validation-testing) in order, tracking progress in `docs/ORCHESTRATION-STATE.md` so you can close your session and resume later — just invoke `@orchestrator` again and it picks up where it left off. It stops and asks before: approving the migration plan, moving past security configuration, and switching traffic for each module. The migration **terminates once the Phase 6 documentation set is produced** — there is no cutover sign-off or decommissioning step. See [agents/orchestrator.agent.md](agents/orchestrator.agent.md) for the full checkpoint list.

You can still invoke any specialist agent directly (below) — useful for re-running a single step, debugging a specific agent's output, or working outside the orchestrator's loop.

---

## How to Invoke Each Agent Directly

### Phase 1 — Audit Agent
Reads `struts-app/`. Produces the migration inventory and audit report. Touches nothing else.

```
@audit
Audit the Struts project at struts-app/. Produce docs/MIGRATION-INVENTORY.md and docs/AUDIT-REPORT.md.
```

### Phase 1 — Planner Agent
Reads the audit output. Produces the migration execution plan with module order and risk register.

```
@planner
Using docs/MIGRATION-INVENTORY.md, produce docs/MIGRATION-PLAN.md with module order, risk register, and phase gates.
```

### Phase 2 — Project Bootstrap Agent
Creates the Spring Boot Maven project structure with dependencies, configuration, and main application class. No controllers or business logic.

```
@project-bootstrap
Create the Spring Boot project at spring-boot-app/ with all dependencies from docs/MIGRATION-PLAN.md. Verify build and health endpoint.
```

### Phase 3 — Route & Configuration Agent
Generates security configuration, interceptor equivalents, exception handling, and application properties.

```
@route-configuration
Generate Spring Boot cross-cutting infrastructure in spring-boot-app/. Match Struts security rules exactly per RULE P3-2.
```

### Phase 4 — Code Transformation Agent (one module at a time)
Transforms Struts Action classes into Spring controllers, extracts services, wires DI.

```
@code-transformation
Migrate {ModuleName} (Module N from docs/MIGRATION-PLAN.md). Transform Action classes to controllers, preserve all business logic.
```

### Phase 5 — View Migration Agent (one module at a time)
Converts JSP files to Thymeleaf templates or converts controllers to @RestController.

```
@view-migration
Migrate the view layer for {ModuleName}. Convert JSP files to Thymeleaf templates. Migrate static assets and error pages.
```

### Quality Gate — Quality Review Agent
Reviews all generated code for correctness, Struts residuals, security issues, and best practices.

```
@quality-review
Review all generated code for {ModuleName}. Produce docs/modules/QUALITY-REPORT-{Module}.md.
```

### Quality Gate — Validation & Testing Agent
Generates and executes the full test suite. Signs off the module for traffic switch.

```
@validation-testing
Generate and run the test suite for {ModuleName}. Produce docs/modules/VALIDATION-TESTING-REPORT.md.
```

### All Phases — Documentation Agent
Produces final migration documentation: architecture report, API mapping, rollback guide, release notes.

```
@documentation
Produce all Phase 6 documentation: ARCHITECTURE-REPORT.md, API-MAPPING.md, ROLLBACK-GUIDE.md, RELEASE-NOTES.md.
```

---

## Agent Catalogue

| Agent | File | Phase | Reads From | Writes To |
|---|---|---|---|---|
| **Orchestrator** | [agents/orchestrator.agent.md](agents/orchestrator.agent.md) | All | `docs/`, `spring-boot-app/`, invokes all other agents | `docs/ORCHESTRATION-STATE.md` |
| **Audit** | [agents/audit.agent.md](agents/audit.agent.md) | 1 | `struts-app/` | `docs/` |
| **Planner** | [agents/planner.agent.md](agents/planner.agent.md) | 1 | `struts-app/`, `docs/` | `docs/` |
| **Project Bootstrap** | [agents/project-bootstrap.agent.md](agents/project-bootstrap.agent.md) | 2 | `docs/` | `spring-boot-app/` |
| **Route & Configuration** | [agents/route-configuration.agent.md](agents/route-configuration.agent.md) | 3 | `struts-app/`, `docs/` | `spring-boot-app/` |
| **Code Transformation** | [agents/code-transformation.agent.md](agents/code-transformation.agent.md) | 4 | `struts-app/`, `docs/` | `spring-boot-app/` |
| **View Migration** | [agents/view-migration.agent.md](agents/view-migration.agent.md) | 5 | `struts-app/`, `docs/` | `spring-boot-app/` |
| **Quality Review** | [agents/quality-review.agent.md](agents/quality-review.agent.md) | 4–5 | `spring-boot-app/`, `docs/` | `docs/modules/` |
| **Validation & Testing** | [agents/validation-testing.agent.md](agents/validation-testing.agent.md) | 4–5 | `spring-boot-app/`, `docs/` | `spring-boot-app/src/test/`, `docs/modules/` |
| **Documentation** | [agents/documentation.agent.md](agents/documentation.agent.md) | All | `docs/modules/` reports | `docs/` |

**One rule for every agent: `struts-app/` is always read-only. No agent ever modifies it.**

---

## Shared Instructions

All agents inherit these shared instruction files automatically via the `applyTo: "**"` frontmatter.

| File | Purpose |
|---|---|
| [instructions/migration-playbook.md](instructions/migration-playbook.md) | Phases 1–6, all mapping tables, pitfalls |
| [instructions/migration-rules.md](instructions/migration-rules.md) | 7 absolute rules + phase gates |
| [instructions/springboot-standards.md](instructions/springboot-standards.md) | Spring Boot patterns, project structure |
| [instructions/coding-guidelines.md](instructions/coding-guidelines.md) | Java coding standards, forbidden patterns |
| [instructions/testing-guidelines.md](instructions/testing-guidelines.md) | Test pyramid, parallel verification, coverage |
| [instructions/documentation-guidelines.md](instructions/documentation-guidelines.md) | Document formats and writing standards |

---

## Agent Collaboration Diagram

The **Orchestrator** sits above every agent below — it is the only agent a human invokes directly. It calls each specialist agent in turn, independently re-verifies each one's Definition of Done, and owns the three ⛔ human checkpoints (`docs/ORCHESTRATION-STATE.md` tracks position across sessions). The migration terminates at Phase 6 documentation delivery.

```
struts-app/ (your Struts source — never modified)
     │
     ▼
┌────────────┐     ┌─────────────┐
│   Audit    │────▶│   Planner   │
│   Agent    │     │   Agent     │
└────────────┘     └──────┬──────┘
  writes:                 │  writes:
  MIGRATION-INVENTORY.md  │  MIGRATION-PLAN.md
  AUDIT-REPORT.md         │
                          ▼
                 ⛔ Checkpoint 1 — human approves MIGRATION-PLAN.md
                          │
             ┌────────────────────────┐
             │  Project Bootstrap     │  writes: spring-boot-app/ structure
             │  Agent (Phase 2)       │           pom.xml, application.properties
             └───────────┬────────────┘           main application class
                         │  (orchestrator verifies build + health itself)
                         ▼
             ┌────────────────────────┐
             │  Route & Configuration │  writes: SecurityConfig, WebConfig
             │  Agent (Phase 3)       │           GlobalExceptionHandler
             └───────────┬────────────┘           application.properties
                         │
                 ⛔ Checkpoint 2 — human verifies security matches Struts exactly
                         │
     ┌───────────────────────────────────────────────┐
     │      Per-Module Loop (Phase 4–5, RULE-3:      │
     │      one module at a time)                    │
     │                                               │
     │  ┌──────────────────┐                         │
     │  │ Code Transform   │──▶ controller/          │
     │  │ Agent            │    service/ model/      │
     │  └────────┬─────────┘                         │
     │           ▼                                   │
     │  ┌──────────────────┐                         │
     │  │ View Migration   │──▶ templates/           │
     │  │ Agent            │    static/ error/       │
     │  └────────┬─────────┘                         │
     │           ▼                                   │
     │  ┌──────────────────┐                         │
     │  │ Quality Review   │──▶ QUALITY-REPORT.md    │
     │  │ Agent            │                         │
     │  └────────┬─────────┘                         │
     │           │ APPROVED (BLOCKED loops back)      │
     │           ▼                                   │
     │  ┌──────────────────┐                         │
     │  │ Validation &     │──▶ src/test/ + report   │
     │  │ Testing Agent    │                         │
     │  └────────┬─────────┘                         │
     │           │ APPROVED (failure loops back)      │
     │           ▼                                   │
     │   ⛔ Checkpoint 3 — human approves traffic     │
     │       switch for this module (orchestrator    │
     │       cannot perform the switch itself)        │
     │           │                                   │
     │    [next module resumes the loop]             │
     └───────────────────────────────────────────────┘
                         │ all modules traffic-switched
                         ▼
             ┌────────────────────────┐
             │  Documentation Agent   │──▶ ARCHITECTURE-REPORT.md
             │  (Phase 6, terminal)   │    API-MAPPING.md
             └────────────────────────┘    ROLLBACK-GUIDE.md
                         │                 RELEASE-NOTES.md
                         ▼
              Migration complete (documentation delivered)
       (no cutover sign-off / decommission — out of scope for this
        framework; struts-app/ is never deleted — RULE-5 guardrail)
```

---

## Absolute Rules (Summary)

Full details: [instructions/migration-rules.md](instructions/migration-rules.md)

| Rule | Prohibits | Enforced By |
|---|---|---|
| **RULE-1** | `ddl-auto=create-drop` or `update` while Struts shares the DB | Route & Config + Quality Review |
| **RULE-2** | Code Transformation before Phase 3 security is verified | Planner (phase gate) |
| **RULE-3** | Migrating more than one module at a time | Code Transformation Agent |
| **RULE-4** | `new ServiceClass()` inside any Spring bean | Code Transformation + Quality Review |
| **RULE-5** | Deleting `struts-app/` within 30 days of cutover | Documentation Agent (Rollback Guide) |
| **RULE-6** | Modifying shared database schema without coordination | Code Transformation Agent |
| **RULE-7** | Switching traffic without approved test report | Validation & Testing Agent |

---

## Phase Gate Checklist

| Gate | Condition | Who Confirms |
|---|---|---|
| Phase 1 → 2 | `MIGRATION-INVENTORY.md` complete, `struts-app/` untouched | Audit Agent |
| Phase 2 → 3 | `spring-boot-app/` builds, `/actuator/health` UP | Project Bootstrap Agent |
| Phase 3 → 4 | Security configured, matches Struts auth behavior exactly | Route & Config Agent |
| Per-module → traffic switch | Quality Report APPROVED + Test Report APPROVED | Quality Review + Validation |
| All modules → Phase 6 | All modules traffic-switched | Orchestrator |
| Phase 6 (terminal) | Full documentation set produced | Documentation Agent |

---

## What This Framework Does NOT Do

- Does not auto-migrate without human review — every phase gate requires approval before the next agent runs
- Does not run database migrations (`ddl-auto` stays `validate`)
- Does not switch nginx/proxy traffic — that is a human-executed change
- Does not delete or modify `struts-app/` — ever
- Does not bypass the one-module-at-a-time rule (RULE-3)
- Does not add authentication that didn't exist in the original app (RULE P3-2)

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 1.0 | 2025-06 | Initial README |
| 1.1 | 2026-07-06 | Added Project Bootstrap Agent (Phase 2), updated agent count to 9, clarified phase gates, simplified invocation examples |
| 1.2 | 2026-07-10 | Added Orchestrator Agent to automate agent sequencing end-to-end; renamed all agent files to `.agent.md`; added `docs/ORCHESTRATION-STATE.md` for cross-session resume; formalized the 5 human-in-the-loop checkpoints |
| 1.3 | 2026-07-13 | Orchestrator now **terminates at Phase 6 documentation delivery**; removed Checkpoint 4 (cutover sign-off) and Checkpoint 5 (decommission) — those activities are out of scope. Three human checkpoints remain (plan approval, security verification, per-module traffic switch). RULE-5 retained as a guardrail (`struts-app/` never deleted). |
