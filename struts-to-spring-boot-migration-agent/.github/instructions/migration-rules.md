---
applyTo: "**"
---

# Migration Rules — Absolute Guardrails

> **Authority:** These rules are derived from the *Struts to Spring Boot Migration Playbook v1.0*.
> Every agent must comply with every rule in this document. No rule may be overridden by any agent, user instruction, or shortcut.

---

## Absolute Rules — No Exceptions

### RULE-1 · Database DDL Safety
`spring.jpa.hibernate.ddl-auto` **must** be set to `validate` or `none` for the entire duration of the migration while the Struts application is running on the same database.

- `create-drop` → destroys existing data. **Forbidden.**
- `update` → can silently alter tables and break the running Struts application. **Forbidden.**
- Only `validate` is safe during co-existence.

**Enforcement:** The Route & Configuration Agent and Quality Review Agent must verify this property before marking any module complete.

---

### RULE-2 · Security Before Business Logic
Spring Security configuration **must** be fully implemented and tested before any Action class is migrated to a Spring controller.

- A migrated endpoint without security is an unauthenticated production endpoint.
- Phase 3 (cross-cutting concerns) must be verified complete before Phase 4 (module migration) begins.

**Enforcement:** The Planner Agent must gate Phase 4 on Phase 3 completion. The Quality Review Agent must verify security coverage for every controller.

---

### RULE-3 · Strangler Fig — No Big-Bang Cutover
Never migrate all modules simultaneously. Migrate one module at a time.

- The Struts application must remain fully operational until every module is verified in Spring Boot.
- Traffic for each module is switched only after that module passes all integration tests.
- Rollback must be available at every stage via reverse-proxy config revert.

**Enforcement:** The Planner Agent must enforce a sequential module order. The Validation & Testing Agent must gate each traffic switch on integration test passage.

---

### RULE-4 · No `new` for Spring Beans
Spring service beans must never be instantiated with `new` inside controllers, actions, or other beans.

- `private PersonService svc = new DefaultPersonService();` → **Forbidden.**
- `@Autowired private PersonService personService;` → **Required.**
- Manual instantiation bypasses `@Transactional`, `@Cacheable`, AOP proxies, and all Spring container features.

**Enforcement:** The Code Transformation Agent must replace every `new ServiceClass()` call. The Quality Review Agent must grep for this pattern and fail if found.

---

### RULE-5 · 30-Day Struts Retention After Cutover
The Struts application must not be deleted or destroyed until Spring Boot has been running stably for a minimum of 30 days with no rollback events.

- After full cutover: keep Struts stopped but deployable.
- After 30 stable days: archive WAR + source to cold storage, then update pipeline.

**Enforcement:** The Documentation Agent must include a 30-day countdown in the Rollback Guide. The Planner Agent must include this gate in the cutover checklist.

---

### RULE-6 · Coordinated Schema Changes
The shared database schema must not be modified during migration without explicit coordination between both the Struts and Spring Boot applications.

- Any schema change must be backward-compatible with the running Struts application.
- Schema changes require a separate coordination checkpoint before execution.

**Enforcement:** The Code Transformation Agent must not generate Flyway/Liquibase migrations that alter existing columns or drop tables. Flag any schema change as a coordination risk.

---

### RULE-7 · Mandatory Per-Module Integration Tests
Per-module integration tests must pass before traffic is switched for that module.

- Unit tests alone are not sufficient to gate a traffic switch.
- Integration tests must run against the shared database.
- Manual smoke tests of all user journeys are required before switching.

**Enforcement:** The Validation & Testing Agent must produce a signed-off integration test report for each module. The Planner Agent must block module promotion without this report.

> **Terminology (Checkpoint 3):** "traffic switch" is the canonical strangler-fig term for **promoting a verified module**. In a proxied deployment it is literally a reverse-proxy traffic switch to Spring Boot; in a local/dev setup (no proxy) the same gate is a **per-module human acceptance** ("module verified → proceed"). Either way the rule is identical: integration tests must pass and a human must accept before the next module starts.

---

## Phase Gate Rules

| Phase | Gate Condition | Blocking Rule |
|-------|---------------|---------------|
| P1 → P2 | Audit inventory complete, no code changed | P1-1 |
| P2 → P3 | Spring Boot starts, health UP, ddl-auto=validate | P2-2, RULE-1 |
| P3 → P4 | All interceptors migrated, security tested | P3-1, RULE-2 |
| P4 module → traffic switch | Integration tests pass, smoke test done | P4-1, RULE-7 |
| P4 → P6 | All modules migrated and traffic-switched | P4-1, RULE-3 |
| P6 (terminal) | Full Phase 6 documentation set produced | — |

> **Scope note:** This framework terminates at Phase 6 documentation delivery. Cutover sign-off, 30-day stability tracking, and decommissioning are **out of scope** — no agent performs them. **RULE-5 below remains an absolute guardrail** (`struts-app/` is never deleted or archived by any agent), it is simply never reached as a gate.

---

## Code Modification Scope Rules

### Read-Only Phases
- **Phase 1 (Audit):** No file in the Struts project may be created, edited, or deleted.
- **Phase 2 (Setup):** Only the new Spring Boot project is created. The Struts project is untouched.

### Struts Project Immutability During Migration
- No agent may modify Struts Action classes, `struts.xml`, JSP files, or any Struts configuration during Phases 1–5.
- The Struts project is a reference, not a work item.

### Spring Boot Project Ownership
- Only agents in Phase 2–5 may write files to the Spring Boot project.
- Each agent has a defined file scope (see individual agent definitions).

---

## Pattern Anti-Rules

The following patterns are forbidden in generated Spring Boot code:

| Forbidden Pattern | Reason | Rule |
|---|---|---|
| `ddl-auto=create-drop` | Destroys data | RULE-1 |
| `ddl-auto=update` | Breaks Struts DB | RULE-1 |
| `new SomeService()` inside a bean | Bypasses Spring DI | RULE-4 |
| `@RestController` without `@RequestMapping` security coverage | Unauthenticated endpoint | RULE-2 |
| Migrating all modules in one PR | Big-bang cutover | RULE-3 |
| Dropping or renaming columns in migrations | Schema breaking change | RULE-6 |
| Switching traffic without integration tests | Untested production change | RULE-7 |
