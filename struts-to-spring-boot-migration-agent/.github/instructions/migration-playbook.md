---
applyTo: "**"
---

# Migration Playbook Reference

> **Source:** Struts to Spring Boot Migration Playbook v1.0, June 2025.
> This document is the condensed reference version for agent use. All agents must treat this as primary source of truth.

---

## Migration Pattern: Strangler Fig

Migrate one module at a time while the Struts application continues to serve traffic. A module is a logical group of related Action classes (e.g., `UserModule`, `ProductModule`, `OrderModule`).

No "big-bang" cutover. Rollback is available at every stage.

---

## Six-Phase Process

### Phase 1 — Audit and Assessment (Read-Only)

**Output:** Migration inventory document.
**Rule P1-1:** No code is changed in this phase. Read and document only.

Audit deliverables:
- Action class inventory (class, methods, fields, interceptors, struts.xml name/namespace)
- `struts.xml` route inventory (action name, namespace, class, method, results, interceptor-refs, exception mappings)
- JSP view inventory + view strategy decision (Thymeleaf or REST)
- Interceptor inventory + purpose classification
- Third-party dependency inventory (Struts-specific libs + Spring Boot equivalents)
- Migration tracker with Status column: Pending / In Progress / Migrated / Verified

Phase 1 is complete when:
- [ ] All Action classes listed with methods and fields
- [ ] All struts.xml routes inventoried
- [ ] All JSP files listed and view strategy decided
- [ ] All interceptors inventoried
- [ ] All Struts-specific dependencies identified
- [ ] Migration tracker created
- [ ] No code changed in the Struts application

---

### Phase 2 — Spring Boot Project Setup

**Rule P2-1:** Spring Boot is a separate Maven artifact. Never merge into the Struts pom.xml.
**Rule P2-2:** `spring.jpa.hibernate.ddl-auto=validate` always. Never `create-drop` or `update`.

Setup steps:
1. Bootstrap via start.spring.io with: Spring Web, Spring Data JPA, DB driver, Thymeleaf (if JSP path) or none (if REST), Spring Security, Spring Boot Actuator, Validation
2. Configure `server.port=8081` (Struts stays on 8080)
3. Point datasource to existing database
4. Copy domain/entity classes — do not modify field names or types
5. Verify: `mvn spring-boot:run` → `GET /actuator/health` returns `{"status":"UP"}`

Phase 2 complete when:
- [ ] Separate Maven artifact created
- [ ] Running on port 8081
- [ ] Connected to existing database
- [ ] `ddl-auto=validate` set
- [ ] Domain/entity classes copied and JPA-annotated
- [ ] Application starts and /actuator/health returns UP
- [ ] No controllers or business logic written yet

---

### Phase 3 — Cross-Cutting Concerns

**Rule P3-1:** Security before business logic. No Action class is migrated until security is configured.
**Rule P3-2:** Spring Security URL protection must replicate Struts interceptor rules exactly.

Interceptor-to-Spring mapping:

| Struts Interceptor | Spring Equivalent | Implementation |
|---|---|---|
| Authentication check | Spring Security filter chain | `SecurityFilterChain @Bean` |
| Logging interceptor | `HandlerInterceptor` | `implements HandlerInterceptor` |
| CORS handler | `CorsConfigurationSource @Bean` | `@CrossOrigin` or global config |
| Transaction wrap | Spring `@Transactional` | `@Transactional` on service methods |
| File upload | `MultipartResolver @Bean` | Built-in via `spring.servlet.multipart` |
| Custom token check | `OncePerRequestFilter` | `extends OncePerRequestFilter` |

Global exception handling — replace `<exception-mapping>` with `@ControllerAdvice`:
```java
@ControllerAdvice
public class GlobalExceptionHandler {
    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {
        return ResponseEntity.status(404).body(new ErrorResponse(ex.getMessage()));
    }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        log.error("Unhandled exception", ex);
        return ResponseEntity.status(500).body(new ErrorResponse("Internal error"));
    }
}
```

Phase 3 complete when:
- [ ] Every Struts interceptor has a Spring equivalent
- [ ] Spring Security matches Struts URL protection rules
- [ ] Protected URLs return 401/403 unauthenticated
- [ ] Public URLs accessible without credentials
- [ ] `GlobalExceptionHandler` covers all exception types
- [ ] All cross-cutting code has unit tests

---

### Phase 4 — Module-by-Module Migration

**Rule P4-1:** One module at a time. Never start Module B until Module A is fully migrated, tested, and traffic-switched.
**Rule P4-2:** Never instantiate services with `new`. Use `@Autowired`.

#### Action Class → Controller Mapping

| Struts 2 | Spring Boot |
|---|---|
| `extends ActionSupport` | `@RestController` / `@Controller` |
| `implements Preparable` | `@ModelAttribute` method |
| `public String execute()` | `@GetMapping` or `@PostMapping` method |
| `return SUCCESS;` | `return ResponseEntity.ok(result);` |
| `return INPUT;` | `return ResponseEntity.badRequest().build();` |
| `return ERROR;` | `throw new AppException();` → `@ControllerAdvice` |
| `ActionContext.getSession()` | `@Autowired HttpSession session` |
| `ServletActionContext.getRequest()` | `@Autowired HttpServletRequest request` |
| Field with getter = view output | `@GetMapping` returns DTO in body |
| `addActionError(msg)` | `throw new ValidationException(msg)` |
| `addFieldError(field, msg)` | `BindingResult` in `@Valid` method param |

#### struts.xml Route → @RequestMapping

| struts.xml pattern | HTTP method | Spring Boot annotation |
|---|---|---|
| `action name="list"` | GET | `@GetMapping("/persons")` |
| `action method="save"` | POST | `@PostMapping("/persons")` |
| `action method="delete"` | POST with param | `@DeleteMapping("/persons/{id}")` |
| `action method="input"` | GET | `@GetMapping("/persons/{id}/edit")` |
| `action name="person-*" method="{1}"` | GET/POST | Explicit `@GetMapping` + `@PostMapping` |
| `namespace="/admin"` | URL prefix | `@RequestMapping("/admin")` on class |

#### Validation Migration

| Struts Validator | Spring Boot Bean Validation |
|---|---|
| `requiredstring` | `@NotBlank(message = "Required")` |
| `email` | `@Email(message = "Invalid email")` |
| `int rangevalidator min/max` | `@Min(1) @Max(100)` |
| `stringlength maxLength=50` | `@Size(max = 50)` |
| Custom `validate()` logic | `implements Validator` or custom `@Constraint` |
| `addFieldError(field, msg)` | `BindingResult.rejectValue(field, code, msg)` |

#### Traffic Switching Per Module (nginx example)
```nginx
location /admin/persons/ {
    proxy_pass http://localhost:8081/admin/persons/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
location / {
    proxy_pass http://localhost:8080;
}
```

Per-module checklist:
- [ ] All Action classes → Spring controllers
- [ ] All struts.xml routes → @RequestMapping
- [ ] Validation migrated and tested
- [ ] prepare() / @ModelAttribute reference data works
- [ ] All result types migrated (views or JSON)
- [ ] Services injected with @Autowired
- [ ] Integration tests pass
- [ ] Manual smoke test: all user journeys end-to-end
- [ ] Security: authenticated + unauthenticated access tested
- [ ] nginx routing updated for this module's URLs
- [ ] Struts action for this module is NOT removed yet

---

### Phase 5 — View Layer Migration

The view strategy is binary and must be decided in Phase 1:
- **Option A:** JSP → Thymeleaf (server-side rendering, faster migration)
- **Option B:** `@RestController` + separate frontend (REST/JSON path)

#### Struts JSP Tag → Thymeleaf

| Struts JSP Tag | Thymeleaf Equivalent | Notes |
|---|---|---|
| `<s:property value="name"/>` | `${person.name}` | EL expression |
| `<s:form action="save">` | `<form th:action="@{/persons/save}">` | CSRF auto-injected |
| `<s:textfield name="person.name">` | `<input type="text" th:field="*{name}">` | @ModelAttribute binding |
| `<s:select name="country" list="countries">` | `<select th:field="*{country}" th:options>` | Requires `th:object` on form |
| `<s:if test="errors.size > 0">` | `<div th:if="${#fields.hasErrors()}">` | Field-level error binding |
| `<s:iterator value="persons">` | `<tr th:each="p : ${persons}">` | Collection iteration |
| `<s:url action="list">` | `<a th:href="@{/persons}">` | URL generation |
| `<s:text name="label.save">` | `<span th:text="#{label.save}">` | i18n message source |

Static assets — move from `src/main/webapp/` to `src/main/resources/static/`.

Phase 5 complete when:
- [ ] View strategy confirmed
- [ ] All JSP views converted OR all controllers converted to @RestController
- [ ] Struts taglib usages replaced
- [ ] Static assets moved
- [ ] Error pages (404, 500) implemented
- [ ] i18n message bundles migrated
- [ ] All UI flows tested end-to-end

---

### Phase 6 — Cutover and Decommission

**Rule P6-1:** Keep Struts stopped-but-deployable for 30 days after cutover.

Full cutover nginx config:
```nginx
location / {
    proxy_pass http://localhost:8081;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Post-cutover monitoring metrics:
- HTTP 5xx error rate (near zero)
- HTTP 4xx rate (watch for 404s = missed URL mappings)
- Response time p50/p95/p99
- Database connection pool usage
- Memory and GC via `/actuator/metrics`

Decommission steps (after 30 stable days):
1. Stop Struts application server
2. Archive WAR + source to cold storage
3. Remove Struts-specific nginx routing
4. Update deployment pipeline to Spring Boot JAR only
5. Remove Struts port (8080) from firewall
6. Update monitoring dashboards

---

## Common Pitfalls Reference

### CSRF Token Mismatch
- Thymeleaf `th:action` forms automatically include CSRF token
- REST/JSON APIs: CSRF can be disabled (non-browser clients)
- Never disable CSRF for Thymeleaf form-based apps

### Session Attribute Differences
- Struts: `ActionContext` stores session data automatically
- Spring Boot: use `@SessionAttributes` on controller or `HttpSession` directly
- Test session persistence across server restarts

### URL Suffix Changes
- Struts: `/persons/list.action` → Spring Boot: `/persons`
- Add 301 nginx redirects for `.action` and `.do` suffix URLs
- Update bookmarks, email templates, external links

### OGNL vs Spring EL
- OGNL: `%{person.name}` → Thymeleaf: `${person.name}`
- OGNL: `%{getText('label.name')}` → Thymeleaf: `#{label.name}`
- Collection access syntax is identical

### Wildcard Method Selection
- Struts: `action name="person-*" method="{1}"` maps to `list()`, `save()`, etc.
- Spring Boot: each method requires an explicit `@RequestMapping` annotation
