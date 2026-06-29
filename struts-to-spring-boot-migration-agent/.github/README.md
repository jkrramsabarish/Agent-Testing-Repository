# Struts to Spring Boot — GitHub Copilot Migration Agents

> **Version:** 1.0 | **Playbook Source:** Struts to Spring Boot Migration Playbook v1.0, June 2025
> **Pattern:** Strangler Fig — one module at a time, rollback available at every stage

This repository is a self-contained workspace. Your Struts project, the generated Spring Boot project, and all migration documents all live here together. The `.github/agents/` directory holds the Copilot agents that read from `struts-app/` and write to `spring-boot-app/`.

---

## Repository Layout

```
struts-to-spring-boot-migration-agent/
│
├── .github/
│   ├── agents/                        ← 8 Copilot Custom Agent definitions
│   │   ├── planner.md
│   │   ├── audit.md
│   │   ├── route-configuration.md
│   │   ├── code-transformation.md
│   │   ├── view-migration.md
│   │   ├── validation-testing.md
│   │   ├── quality-review.md
│   │   └── documentation.md
│   ├── instructions/                  ← 6 shared instruction files (all agents reference these)
│   │   ├── migration-playbook.md
│   │   ├── migration-rules.md
│   │   ├── springboot-standards.md
│   │   ├── coding-guidelines.md
│   │   ├── testing-guidelines.md
│   │   └── documentation-guidelines.md
│   └── README.md                      ← this file
│
├── struts-app/                        ← PUT YOUR STRUTS PROJECT HERE (agents read, never write)
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/
│   │   │   │   └── com/example/
│   │   │   │       ├── action/        ← Action classes
│   │   │   │       ├── service/       ← Service layer
│   │   │   │       ├── dao/           ← DAO layer
│   │   │   │       └── model/         ← Domain model / entities
│   │   │   ├── resources/
│   │   │   │   └── struts.xml         ← Route configuration
│   │   │   └── webapp/
│   │   │       └── WEB-INF/
│   │   │           └── jsp/           ← JSP view files
│   │   └── test/
│   └── pom.xml
│
├── spring-boot-app/                   ← GENERATED SPRING BOOT PROJECT (agents write here)
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/example/
│   │   │   │   ├── config/            ← SecurityConfig, WebMvcConfig
│   │   │   │   ├── controller/        ← Migrated controllers
│   │   │   │   ├── service/           ← Migrated services
│   │   │   │   ├── repository/        ← Spring Data JPA repositories
│   │   │   │   ├── entity/            ← JPA-annotated entities
│   │   │   │   ├── dto/               ← Request / Response DTOs
│   │   │   │   ├── exception/         ← Custom exceptions + GlobalExceptionHandler
│   │   │   │   └── filter/            ← OncePerRequestFilter implementations
│   │   │   └── resources/
│   │   │       ├── application.properties
│   │   │       ├── static/            ← CSS, JS, images (migrated from struts-app)
│   │   │       └── templates/         ← Thymeleaf HTML templates
│   │   └── test/
│   │       └── java/com/example/
│   │           ├── controller/        ← @WebMvcTest tests
│   │           ├── service/           ← Unit tests
│   │           └── integration/       ← @SpringBootTest tests
│   └── pom.xml
│
└── docs/                              ← ALL MIGRATION DOCUMENTS LAND HERE
    ├── MIGRATION-INVENTORY.md         ← Audit Agent → maintained by Documentation Agent
    ├── MIGRATION-PLAN.md              ← Planner Agent
    ├── AUDIT-REPORT.md                ← Audit Agent
    ├── URL-MAPPING.md                 ← Route & Configuration Agent
    ├── API-MAPPING.md                 ← Documentation Agent (cumulative)
    ├── ROLLBACK-GUIDE.md              ← Documentation Agent (before Phase 6 cutover)
    ├── ARCHITECTURE-REPORT.md         ← Documentation Agent (Phase 6 completion)
    ├── RELEASE-NOTES.md               ← Documentation Agent (Phase 6 cutover)
    ├── POST-MIGRATION-SUMMARY.md      ← Documentation Agent (after 30 days)
    └── modules/                       ← Per-module sign-off documents
        ├── MODULE-COMPLETION-{Module}.md
        ├── MODULE-TEST-REPORT-{Module}.md
        └── QUALITY-REPORT-{Module}.md
```

---

## Setup — Before You Start

**Step 1 — Drop your Struts project in:**
```bash
# Copy (or clone) your existing Struts WAR project into struts-app/
# Example:
cp -r /path/to/your/legacy-struts-project/* struts-to-spring-boot-migration-agent/struts-app/
```
The `struts-app/` folder must contain your real Struts source code — `struts.xml`, Action classes, JSP files, `pom.xml`. No agents will modify anything inside it.

**Step 2 — Open in VS Code:**
```bash
code struts-to-spring-boot-migration-agent/
```
Open the single root folder. GitHub Copilot sees the entire workspace including `struts-app/` and `spring-boot-app/`.

**Step 3 — Enable Copilot Agent mode:**
In Copilot Chat, switch from Ask to **Agent** mode using the mode selector at the bottom of the chat panel. This activates custom agent definitions from `.github/agents/`.

---

## How to Invoke Each Agent

### Phase 1 — Audit Agent
Reads `struts-app/`. Writes `docs/MIGRATION-INVENTORY.md` and `docs/AUDIT-REPORT.md`. Touches nothing else.

```
@audit

Audit the Struts project at struts-app/.

Read:
- struts-app/src/main/resources/struts.xml
- struts-app/src/main/java/ (all Action, Service, DAO, model classes)
- struts-app/src/main/webapp/WEB-INF/jsp/ (all JSP files)
- struts-app/pom.xml

Write output to:
- docs/MIGRATION-INVENTORY.md
- docs/AUDIT-REPORT.md
```

---

### Phase 1 — Planner Agent
Reads `docs/MIGRATION-INVENTORY.md`. Writes `docs/MIGRATION-PLAN.md`.

```
@planner

Using docs/MIGRATION-INVENTORY.md produced by the Audit Agent,
analyse the Struts project structure in struts-app/ and produce
the migration execution plan.

Write output to:
- docs/MIGRATION-PLAN.md
```

---

### Phase 2 — Spring Boot Project Bootstrap *(human step)*
Create the `spring-boot-app/` Maven project using start.spring.io or your IDE.
Dependencies: Spring Web, Spring Data JPA, DB driver, Thymeleaf (if JSP path), Spring Security, Spring Boot Actuator, Validation.
Configure `server.port=8081`. Do not write any controllers yet.

---

### Phase 3 — Route & Configuration Agent
Reads `struts-app/` config files and `docs/MIGRATION-INVENTORY.md`. Writes into `spring-boot-app/`.

```
@route-configuration

Generate the Spring Boot cross-cutting infrastructure for spring-boot-app/.

Read:
- struts-app/src/main/resources/struts.xml          (exception mappings, interceptor stacks)
- struts-app/src/main/webapp/WEB-INF/web.xml        (filters, listeners)
- struts-app/src/main/resources/applicationContext.xml  (datasource config)
- docs/MIGRATION-INVENTORY.md                        (interceptor and security inventory)

Write to spring-boot-app/:
- src/main/resources/application.properties
- src/main/resources/application-dev.properties
- src/main/resources/application-prod.properties
- src/main/java/.../config/SecurityConfig.java
- src/main/java/.../config/WebMvcConfig.java
- src/main/java/.../exception/GlobalExceptionHandler.java
- src/main/java/.../exception/*.java                 (one per exception type)
- src/main/java/.../dto/ErrorResponse.java
- src/main/java/.../filter/*.java                    (one per Struts interceptor)
- docs/URL-MAPPING.md
```

---

### Phase 4 — Code Transformation Agent *(one module at a time)*
Reads from `struts-app/`. Writes into `spring-boot-app/`. Invoke once per module.

```
@code-transformation

Migrate the PersonModule (Module 1 from docs/MIGRATION-PLAN.md).

Read from struts-app/:
- src/main/java/com/example/action/PersonAction.java
- src/main/java/com/example/service/PersonService.java
- src/main/java/com/example/service/impl/PersonServiceImpl.java
- src/main/java/com/example/dao/PersonDAO.java
- src/main/java/com/example/model/Person.java
- src/main/resources/struts.xml                      (person-* action entries only)
- src/main/resources/PersonAction-validation.xml      (if it exists)

Read docs/:
- docs/MIGRATION-INVENTORY.md                        (module scope and view strategy)

Write to spring-boot-app/src/main/java/com/example/:
- controller/PersonController.java
- service/PersonService.java
- service/impl/PersonServiceImpl.java
- repository/PersonRepository.java
- entity/Person.java
- dto/PersonRequest.java
- dto/PersonResponse.java

Update docs/MIGRATION-INVENTORY.md: set PersonModule status to Migrated.
```

---

### Phase 5 — View Migration Agent *(one module at a time)*
Reads JSP files from `struts-app/`. Writes Thymeleaf templates into `spring-boot-app/`.

```
@view-migration

Migrate the view layer for PersonModule.
View strategy for this module: Thymeleaf  (from docs/MIGRATION-INVENTORY.md)

Read from struts-app/:
- src/main/webapp/WEB-INF/jsp/person/list.jsp
- src/main/webapp/WEB-INF/jsp/person/edit.jsp
- src/main/webapp/css/         (static assets)
- src/main/webapp/js/
- src/main/resources/ApplicationResources.properties  (i18n)

Write to spring-boot-app/:
- src/main/resources/templates/person/list.html
- src/main/resources/templates/person/edit.html
- src/main/resources/templates/error/404.html         (if not already created)
- src/main/resources/static/css/                      (copied assets)
- src/main/resources/static/js/
- src/main/resources/messages.properties
```

---

### Phase 4/5 — Quality Review Agent *(after each module's code + views are generated)*
Reads `spring-boot-app/` — never writes code. Writes `docs/modules/QUALITY-REPORT-{Module}.md`.

```
@quality-review

Review all generated code for PersonModule.

Read from spring-boot-app/src/main/java/com/example/:
- controller/PersonController.java
- service/impl/PersonServiceImpl.java
- repository/PersonRepository.java
- entity/Person.java
- dto/PersonRequest.java
- dto/PersonResponse.java
- config/SecurityConfig.java
- exception/GlobalExceptionHandler.java

Read:
- spring-boot-app/src/main/resources/application.properties
- spring-boot-app/src/main/resources/templates/person/
- docs/MIGRATION-INVENTORY.md   (Struts interceptor URL rules for security cross-check)

Write:
- docs/modules/QUALITY-REPORT-Person.md
```

---

### Phase 4/5 — Validation & Testing Agent *(after Quality Review is APPROVED)*
Reads `spring-boot-app/` source. Writes test files into `spring-boot-app/src/test/` and reports into `docs/modules/`.

```
@validation-testing

Generate and run the full test suite for PersonModule.

Read:
- spring-boot-app/src/main/java/com/example/controller/PersonController.java
- spring-boot-app/src/main/java/com/example/service/impl/PersonServiceImpl.java
- docs/MIGRATION-INVENTORY.md   (user journeys to cover in integration tests)
- docs/modules/QUALITY-REPORT-Person.md   (must be APPROVED before running)

Write to spring-boot-app/src/test/java/com/example/:
- service/PersonServiceImplTest.java
- controller/PersonControllerTest.java
- integration/PersonIntegrationTest.java

Write:
- docs/modules/MODULE-TEST-REPORT-Person.md
```

---

### All phases — Documentation Agent
Reads all reports. Writes all `.md` documents in `docs/`. Never touches Java or template files.

```
@documentation

Update docs/MIGRATION-INVENTORY.md — set PersonModule status to Verified.
Produce docs/modules/MODULE-COMPLETION-Person.md using:
- docs/modules/QUALITY-REPORT-Person.md
- docs/modules/MODULE-TEST-REPORT-Person.md
- docs/MIGRATION-INVENTORY.md (PersonModule component list)
```

At Phase 6 cutover:
```
@documentation

Produce the following using all module completion reports and the full inventory:
- docs/ROLLBACK-GUIDE.md
- docs/ARCHITECTURE-REPORT.md
- docs/RELEASE-NOTES.md
- docs/API-MAPPING.md (final accumulated version)
```

---

## Agent Catalogue

| Agent | File | Phase | Reads From | Writes To |
|---|---|---|---|---|
| **Audit** | [agents/audit.md](agents/audit.md) | 1 | `struts-app/` | `docs/` |
| **Planner** | [agents/planner.md](agents/planner.md) | 1 | `struts-app/`, `docs/` | `docs/` |
| **Route & Configuration** | [agents/route-configuration.md](agents/route-configuration.md) | 3 | `struts-app/`, `docs/` | `spring-boot-app/` |
| **Code Transformation** | [agents/code-transformation.md](agents/code-transformation.md) | 4 | `struts-app/`, `docs/` | `spring-boot-app/` |
| **View Migration** | [agents/view-migration.md](agents/view-migration.md) | 5 | `struts-app/`, `docs/` | `spring-boot-app/` |
| **Quality Review** | [agents/quality-review.md](agents/quality-review.md) | 4–5 | `spring-boot-app/`, `docs/` | `docs/modules/` |
| **Validation & Testing** | [agents/validation-testing.md](agents/validation-testing.md) | 4–5 | `spring-boot-app/`, `docs/` | `spring-boot-app/src/test/`, `docs/modules/` |
| **Documentation** | [agents/documentation.md](agents/documentation.md) | All | `docs/modules/` reports | `docs/` |

**One rule for every agent: `struts-app/` is always read-only. No agent ever modifies it.**

---

## Shared Instructions

All agents inherit these shared instruction files automatically via the `applyTo: "**"` frontmatter. You never need to attach them manually in Copilot Chat.

| File | Purpose |
|---|---|
| [instructions/migration-playbook.md](instructions/migration-playbook.md) | Phases 1–6, all mapping tables, pitfalls |
| [instructions/migration-rules.md](instructions/migration-rules.md) | 7 absolute rules + phase gates |
| [instructions/springboot-standards.md](instructions/springboot-standards.md) | Spring Boot 3.x patterns, project structure |
| [instructions/coding-guidelines.md](instructions/coding-guidelines.md) | Java coding standards, forbidden patterns |
| [instructions/testing-guidelines.md](instructions/testing-guidelines.md) | Test pyramid, parallel verification, coverage |
| [instructions/documentation-guidelines.md](instructions/documentation-guidelines.md) | Document formats and writing standards |

---

## Agent Collaboration Diagram

```
struts-app/ (your Struts source — never modified)
     │
     ▼
┌────────────┐     ┌─────────────┐
│ Audit      │────▶│  Planner    │
│ Agent      │     │  Agent      │
└────────────┘     └──────┬──────┘
  writes:                 │  writes:
  docs/MIGRATION-         │  docs/MIGRATION-
  INVENTORY.md            │  PLAN.md
  docs/AUDIT-REPORT.md    │
                          ▼
             ┌────────────────────────┐
             │  Route & Configuration │  writes: spring-boot-app/config/
             │  Agent                 │           spring-boot-app/resources/
             └───────────┬────────────┘           docs/URL-MAPPING.md
                         │
                ── Phase 3 gate ──
                         │
     ┌───────────────────────────────────────────────┐
     │         Per-Module Loop (Phase 4–5)           │
     │                                               │
     │  struts-app/{module}                          │
     │       │                                       │
     │       ▼                                       │
     │  ┌──────────────────┐                         │
     │  │ Code Transform   │──▶ spring-boot-app/     │
     │  │ Agent            │    controller/           │
     │  └────────┬─────────┘    service/             │
     │           │              repository/           │
     │           ▼              entity/ dto/          │
     │  ┌──────────────────┐                         │
     │  │ View Migration   │──▶ spring-boot-app/     │
     │  │ Agent            │    templates/            │
     │  └────────┬─────────┘    static/              │
     │           │                                   │
     │           ▼                                   │
     │  ┌──────────────────┐                         │
     │  │ Quality Review   │──▶ docs/modules/        │
     │  │ Agent            │    QUALITY-REPORT-X.md  │
     │  └────────┬─────────┘                         │
     │           │ APPROVED                          │
     │           ▼                                   │
     │  ┌──────────────────┐                         │
     │  │ Validation &     │──▶ spring-boot-app/test/│
     │  │ Testing Agent    │    docs/modules/        │
     │  └────────┬─────────┘    MODULE-TEST-REPORT-X │
     │           │ APPROVED                          │
     │           ▼                                   │
     │  ┌──────────────────┐                         │
     │  │ Documentation    │──▶ docs/modules/        │
     │  │ Agent            │    MODULE-COMPLETION-X  │
     │  └──────────────────┘                         │
     │           │                                   │
     │    [traffic switch — human]                   │
     │           │                                   │
     │    [next module]                              │
     └───────────────────────────────────────────────┘
                         │ all modules done
                         ▼
             ┌────────────────────┐
             │  Documentation     │──▶ docs/ROLLBACK-GUIDE.md
             │  Agent (Phase 6)   │    docs/ARCHITECTURE-REPORT.md
             └────────────────────┘    docs/RELEASE-NOTES.md
                         │ 30 days stable
                         ▼
             ┌────────────────────┐
             │  Documentation     │──▶ docs/POST-MIGRATION-SUMMARY.md
             │  Agent (Final)     │
             └────────────────────┘
```

---

## Absolute Rules (Summary)

Full details: [instructions/migration-rules.md](instructions/migration-rules.md)

| Rule | Prohibits | Enforced By |
|---|---|---|
| **RULE-1** | `ddl-auto=create-drop` or `update` in `spring-boot-app/` while Struts DB is shared | Route & Config + Quality Review |
| **RULE-2** | Code Transformation runs before Phase 3 security is verified | Planner (phase gate) |
| **RULE-3** | Migrating more than one module at a time | Code Transformation Agent |
| **RULE-4** | `new ServiceClass()` inside any Spring bean | Code Transformation + Quality Review |
| **RULE-5** | Deleting `struts-app/` within 30 days of cutover | Documentation Agent (Rollback Guide) |
| **RULE-6** | Modifying shared database schema without coordination | Code Transformation Agent |
| **RULE-7** | Switching traffic without `MODULE-TEST-REPORT-{Module}.md` status APPROVED | Validation & Testing Agent |

---

## Phase Gate Checklist

| Gate | Condition | Who Confirms |
|---|---|---|
| Phase 1 → 2 | `docs/MIGRATION-INVENTORY.md` complete, `struts-app/` untouched | Audit Agent |
| Phase 2 → 3 | `spring-boot-app/` starts, `/actuator/health` UP, `ddl-auto=validate` | Human + Route & Config Agent |
| Phase 3 → 4 | Security tested, all interceptors have Spring equivalents | Validation & Testing Agent |
| Per-module → traffic switch | `QUALITY-REPORT-X.md` = APPROVED + `MODULE-TEST-REPORT-X.md` = APPROVED | Quality Review + Validation & Testing |
| All modules → Phase 6 cutover | Full regression test passes | Validation & Testing Agent |
| Cutover → Struts decommission | 30 stable days, zero rollback events | Documentation Agent (30-day tracker) |

---

## What This Framework Does NOT Do

- Does not auto-migrate — every phase gate requires human review and approval before the next agent runs
- Does not run database migrations (`ddl-auto` stays `validate` in `spring-boot-app/application.properties`)
- Does not switch nginx/proxy traffic — that is a human-executed change
- Does not delete or modify `struts-app/` — ever
- Does not bypass the one-module-at-a-time rule (RULE-3)
