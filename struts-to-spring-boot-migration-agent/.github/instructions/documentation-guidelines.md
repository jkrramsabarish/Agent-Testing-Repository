---
applyTo: "**"
---

# Documentation Guidelines

> **Scope:** Standards for all migration documentation produced by the Documentation Agent and referenced by other agents.
> Every document must be immediately usable by developers who were not part of the migration.

---

## Document Categories

| Document | Audience | Updated When |
|---|---|---|
| Migration Inventory | Migration team | Phase 1 (Audit) — updated every phase |
| Migration Plan | Tech lead, PM | Phase 1 planning |
| Module Completion Report | Migration team, QA | Each module completes Phase 4 |
| Architecture Report | Architects, new team members | Phase 6 completion |
| API Mapping Document | Frontend, integration teams | Each module completes Phase 4 |
| Release Notes | All stakeholders | Phase 6 cutover |
| Rollback Guide | Ops, on-call engineers | Phase 6 preparation |
| Post-Migration Summary | Management, auditors | After 30-day stable period |

---

## Migration Inventory Document

### Purpose
Single source of truth for all components requiring migration. Lives in the repository root as `MIGRATION-INVENTORY.md`.

### Required Sections

#### Action Class Inventory Table
```markdown
| Class | Package | Methods | Input Fields | Output Fields | Interceptors | Struts Action Name | Namespace | Status |
|---|---|---|---|---|---|---|---|---|
| PersonAction | org.example.action | execute, list, save, delete | firstName, email | persons, person | defaultStack | person-* | /admin | Pending |
```

Status values: `Pending` → `In Progress` → `Migrated` → `Verified`

#### struts.xml Route Inventory Table
```markdown
| Action Name | Namespace | Class | Method | Results | Interceptor Refs | Exception Mappings | Status |
|---|---|---|---|---|---|---|---|
| person-list | /admin | PersonAction | list | success→list.jsp, error→error.jsp | defaultStack | AppException→error | Pending |
```

#### View Inventory Table
```markdown
| JSP File | Struts Tags Used | View Strategy | Target | Status |
|---|---|---|---|---|
| /WEB-INF/jsp/person/list.jsp | s:iterator, s:url, s:property | Thymeleaf | templates/person/list.html | Pending |
```

#### Interceptor Inventory Table
```markdown
| Interceptor Class | Purpose | Spring Equivalent | Implementation Class | Status |
|---|---|---|---|---|
| AuthCheckInterceptor | Authentication | SecurityFilterChain | SecurityConfig.filterChain() | Pending |
```

#### Dependency Inventory Table
```markdown
| Struts Dependency | Version | Spring Boot Equivalent | Action Required |
|---|---|---|---|
| struts2-core | 2.5.x | spring-boot-starter-web | Remove |
| struts2-json-plugin | 2.5.x | Built-in Jackson | Remove |
```

---

## Module Completion Report

### Purpose
Sign-off document for each module before traffic switch. Produced by the Documentation Agent after the Validation & Testing Agent signs off.

### Template
```markdown
# Module Completion Report: {ModuleName}

**Date:** {YYYY-MM-DD}
**Migration Engineer:** {name}
**Reviewed By:** {name}

## Summary
Brief description of what was migrated.

## Components Migrated
- [ ] Action classes: {list}
- [ ] struts.xml routes: {list}
- [ ] Views: {list}
- [ ] Interceptors: {list}
- [ ] Services: {list}

## Test Results
| Test Type | Total | Passed | Failed |
|---|---|---|---|
| Unit Tests | X | X | 0 |
| Controller Slice Tests | X | X | 0 |
| Integration Tests | X | X | 0 |
| Security Tests | X | X | 0 |

## Parallel Verification
- Struts response captured: [ ]
- Spring Boot response captured: [ ]
- Responses match: [ ]
- Differences noted: {none / list differences}

## Rollback Test
- Traffic switched to Spring Boot: [ ]
- Traffic reverted to Struts: [ ]
- Rollback time: {X minutes} (must be < 5 minutes)

## URL Mapping Changes
| Old Struts URL | New Spring Boot URL | Redirect Configured |
|---|---|---|
| /admin/persons/list.action | /admin/persons | [ ] |

## Security Verification
- All protected URLs return 401/403 when unauthenticated: [ ]
- All public URLs accessible without credentials: [ ]
- Spring Security rules match Struts interceptor rules: [ ]

## Sign-Off Checklist
- [ ] All Action classes → Spring controllers (complete)
- [ ] All routes → @RequestMapping (complete)
- [ ] Validation migrated and tested
- [ ] Views migrated (Thymeleaf / REST)
- [ ] Services use @Autowired injection
- [ ] Integration tests pass
- [ ] Security tests pass
- [ ] Parallel verification: outputs match
- [ ] Rollback tested and timed
- [ ] nginx routing updated

**Status:** APPROVED / BLOCKED (reason: ...)
```

---

## API Mapping Document

### Purpose
Documents every URL change from Struts to Spring Boot for frontend and integration teams.

### Template
```markdown
# API Mapping: {Module}

## Endpoint Changes
| Old URL (Struts) | Method | New URL (Spring Boot) | Method | Notes |
|---|---|---|---|---|
| /admin/persons/list.action | GET | /api/persons | GET | Response format changed to JSON array |
| /admin/person-save.action | POST | /api/persons | POST | Body now JSON, not form params |
| /admin/person-delete.action | POST | /api/persons/{id} | DELETE | ID now path variable |

## Request Format Changes
### Create Person
**Before (Struts form POST):**
```
POST /admin/person-save.action
Content-Type: application/x-www-form-urlencoded

firstName=Alice&lastName=Smith&email=alice@example.com
```
**After (Spring Boot JSON):**
```
POST /api/persons
Content-Type: application/json

{"firstName": "Alice", "lastName": "Smith", "email": "alice@example.com"}
```

## Response Format Changes
### List Persons
**Before (Struts redirect + JSP):** Server-rendered HTML
**After (Spring Boot JSON):**
```json
[{"id": 1, "firstName": "Alice", "email": "alice@example.com"}]
```

## Backward Compatibility
- 301 redirects configured for all .action URLs: [ ]
- Old URL patterns documented: [ ]
```

---

## Rollback Guide

### Purpose
Step-by-step runbook for on-call engineers to revert traffic to Struts. Must be executable by someone who was not part of the migration.

### Template
```markdown
# Rollback Guide

**Last Updated:** {date}
**Rollback Window:** 30 days from cutover date ({cutover date})
**Struts Application Status:** Stopped but deployable on port 8080

## When to Rollback
- HTTP 5xx error rate > 1% sustained for 5 minutes
- Critical business functionality broken
- Data integrity issue detected

## Rollback Steps

### Step 1: Start Struts Application (2 minutes)
```bash
cd /opt/struts-app
./start.sh
# Verify: curl http://localhost:8080/actuator/health
```

### Step 2: Update Reverse Proxy (1 minute)
```bash
# Edit nginx config
sudo nano /etc/nginx/conf.d/app.conf

# Change:
#   proxy_pass http://localhost:8081;
# To:
#   proxy_pass http://localhost:8080;

sudo nginx -t && sudo nginx -s reload
```

### Step 3: Verify Rollback (1 minute)
```bash
curl http://yourdomain.com/admin/persons/list.action
# Expected: 200 OK from Struts
```

### Step 4: Notify Team
- Post in #ops-alerts Slack channel
- Create incident ticket
- Page migration engineer

## Spring Boot Decommission Timeline
- Cutover date: {date}
- 30-day review window ends: {date + 30 days}
- Archive Struts after: {date + 30 days} if no rollback events
```

---

## Writing Standards

### Clarity Rules
- Write for an engineer who was not part of this migration
- Define every acronym on first use
- Use tables for comparisons (before/after, Struts vs Spring Boot)
- Use numbered lists for sequential steps
- Use bullet points for unordered facts
- Use code blocks for all commands and code snippets

### Version Control
- Every document must include a `Last Updated` date
- Document the version of the migration playbook used
- Track changes in a `Changelog` section at the bottom of long-lived documents

### Markdown Format Rules
- H1 (`#`) for document title only
- H2 (`##`) for major sections
- H3 (`###`) for subsections
- Use `**bold**` for critical warnings or rule names
- Use `` `code` `` for class names, method names, annotations, commands
- Use fenced code blocks with language tags for all code snippets

### Anti-Patterns

| Anti-Pattern | Problem |
|---|---|
| Vague status ("done", "complete") | Not actionable; use checklist items |
| Missing dates on reports | Not auditable |
| Documenting only the happy path | Incomplete; include error cases |
| No rollback instructions | Risk on cutover |
| Copy-paste from code comments | Duplicate information; use code links |
| Technical jargon without explanation | Inaccessible to stakeholders |
| Documents not in version control | Not auditable |
