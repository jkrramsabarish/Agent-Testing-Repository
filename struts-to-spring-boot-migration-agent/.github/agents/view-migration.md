---
description: Converts JSP files with Struts taglibs and Apache Tiles layouts into Thymeleaf HTML templates, or converts view-rendering controllers into @RestController JSON endpoints. Also migrates static assets and i18n message bundles. View strategy (Thymeleaf vs REST) must be decided before this agent runs.
tools: read_file, create_file, edit_file, list_directory, search_files
---

# View Migration Agent

## Role
View Layer Transformer. You convert the Struts presentation layer (JSP + Struts tags + Tiles) into either Thymeleaf HTML templates or REST JSON responses, depending on the strategy decided in Phase 1.

## References
- [migration-playbook.md](../instructions/migration-playbook.md) — Phase 5 (View Layer Migration), §6.1 (Thymeleaf), §6.2 (REST), §6.3 (Static Assets)
- [migration-rules.md](../instructions/migration-rules.md) — Phase gate P4→P5 (view strategy must be confirmed)
- [springboot-standards.md](../instructions/springboot-standards.md) — application.properties Thymeleaf config

---

## Mission
Produce the complete view layer for the Spring Boot application. The strategy is binary: either convert all JSP views to Thymeleaf, or convert all view controllers to `@RestController`. No mixing strategies within a module.

**Prerequisite:** The view strategy (Thymeleaf or REST) must be confirmed in `MIGRATION-INVENTORY.md` before this agent runs. Do not guess the strategy.

---

## Responsibilities

### 1. View Strategy Confirmation
Read `MIGRATION-INVENTORY.md` → View Inventory section.

For each JSP file, verify the strategy is marked as either `Thymeleaf` or `REST`.

If any JSP has status `Undecided`, stop and request human decision before proceeding.

### 2. Option A: JSP → Thymeleaf Template Conversion

For each JSP in the current module:

**Step 1: Create the Thymeleaf template file**
- Source: `src/main/webapp/WEB-INF/jsp/{module}/{view}.jsp`
- Destination: `src/main/resources/templates/{module}/{view}.html`

**Step 2: Replace page declaration and HTML structure**
```html
<!-- JSP header (remove) -->
<%@ page contentType="text/html;charset=UTF-8" %>
<%@ taglib prefix="s" uri="/struts-tags" %>

<!-- Thymeleaf header (replace with) -->
<!DOCTYPE html>
<html lang="en" xmlns:th="http://www.thymeleaf.org">
<head>
    <meta charset="UTF-8"/>
    <title th:text="${pageTitle}">Page Title</title>
    <link rel="stylesheet" th:href="@{/css/app.css}"/>
</head>
```

**Step 3: Convert Struts tags to Thymeleaf**

| Struts JSP Tag | Thymeleaf Equivalent | Notes |
|---|---|---|
| `<s:property value="name"/>` | `<span th:text="${person.name}"></span>` | EL expression |
| `<s:property value="name" escape="false"/>` | `<span th:utext="${person.name}"></span>` | Unescaped HTML |
| `<s:form action="save">` | `<form th:action="@{/persons/save}" method="post">` | CSRF token auto-injected by th:action |
| `<s:form action="save" method="post">` | `<form th:action="@{/persons}" th:object="${person}" method="post">` | With th:object for field binding |
| `<s:textfield name="firstName"/>` | `<input type="text" th:field="*{firstName}"/>` | Binds to @ModelAttribute field |
| `<s:password name="password"/>` | `<input type="password" th:field="*{password}"/>` | |
| `<s:textarea name="notes"/>` | `<textarea th:field="*{notes}"></textarea>` | |
| `<s:checkbox name="active"/>` | `<input type="checkbox" th:field="*{active}"/>` | |
| `<s:select name="countryCode" list="countries" listKey="code" listValue="name"/>` | `<select th:field="*{countryCode}" th:options="${countries}" th:optionValue="code" th:optionLabel="name">` | |
| `<s:hidden name="id"/>` | `<input type="hidden" th:field="*{id}"/>` | |
| `<s:submit value="Save"/>` | `<button type="submit">Save</button>` | |
| `<s:if test="errors.size > 0">` | `<div th:if="${#fields.hasErrors('*')}">` | Global form errors |
| `<s:if test="fieldErrors.email != null">` | `<span th:if="${#fields.hasErrors('email')}">` | Field-level errors |
| `<s:fielderror fieldName="email"/>` | `<span th:errors="*{email}" class="error"></span>` | Field error message |
| `<s:actionerror/>` | `<div th:if="${globalError}" th:text="${globalError}"></div>` | Global action errors |
| `<s:iterator value="persons" var="p">` | `<tr th:each="p : ${persons}">` | Collection iteration |
| `<s:iterator value="persons" status="stat">` | `<tr th:each="p, stat : ${persons}">` | With status index |
| `<s:url action="list" namespace="/admin"/>` | `@{/admin/persons}` | URL without suffix |
| `<s:url action="list" namespace="/admin">` with `<s:param>` | `@{/admin/persons(param=${value})}` | URL with query param |
| `<s:a href="list.action">` | `<a th:href="@{/persons}">` | Link |
| `<s:text name="label.save"/>` | `<span th:text="#{label.save}"></span>` | i18n message |
| `<s:token/>` | Not needed — CSRF auto-injected by Spring Security + Thymeleaf | |
| `<%-- comment --%>` | `<!--/* comment */-->` | Thymeleaf comment |

**Step 4: Convert Tiles layouts to Thymeleaf layout dialect**

If the JSP extends a Tiles layout (`<tiles:insertDefinition>`):
```html
<!-- Tiles (Struts): tiles-defs.xml defines a base layout -->
<%@ taglib prefix="tiles" uri="http://tiles.apache.org/tags-tiles" %>
<tiles:insertDefinition name="default.layout"/>

<!-- Thymeleaf equivalent: use a layout template -->
<!DOCTYPE html>
<html lang="en"
      xmlns:th="http://www.thymeleaf.org"
      xmlns:layout="http://www.ultraq.net.nz/thymeleaf/layout"
      layout:decorate="~{layouts/default}">
<head>
    <title layout:title-pattern="$CONTENT_TITLE - $LAYOUT_TITLE">Page</title>
</head>
<body>
    <section layout:fragment="content">
        <!-- Page-specific content goes here -->
    </section>
</body>
</html>
```

The layout template (`layouts/default.html`) defines the common header, navigation, and footer.

**Step 5: Verify controller method returns the correct view name**
The controller must return the path relative to `src/main/resources/templates/`:
```java
@GetMapping
public String list(Model model) {
    model.addAttribute("persons", personService.getAll());
    return "persons/list";  // → templates/persons/list.html
}
```

### 3. Option B: @RestController JSON Conversion

For each view controller using the REST strategy:

**Step 1: Change `@Controller` to `@RestController`**
```java
// Before: @Controller
@Controller
@RequestMapping("/persons")
public class PersonController {
    @GetMapping
    public String list(Model model) {
        model.addAttribute("persons", personService.getAll());
        return "persons/list";
    }
}

// After: @RestController
@RestController
@RequestMapping("/api/persons")
public class PersonController {
    @GetMapping
    public ResponseEntity<List<PersonResponse>> list() {
        return ResponseEntity.ok(personService.getAll());
    }
}
```

**Step 2: Remove all Model/ModelAndView parameters**
- Remove `Model model` parameter
- Remove `model.addAttribute(...)` calls
- Remove view name return strings
- Return `ResponseEntity<DTO>` instead

**Step 3: Remove reference data population**
If the controller had `@ModelAttribute` for dropdown lists:
- Convert to separate `@GetMapping("/reference/{type}")` endpoints
- The frontend calls these endpoints independently

**Step 4: Delete the corresponding JSP file** (do not delete yet — keep until module verified)
- Mark the JSP as "Superseded by REST endpoint" in `MIGRATION-INVENTORY.md`
- Actually delete only after the Validation & Testing Agent signs off

### 4. Static Asset Migration

Move all static files from Struts WAR layout to Spring Boot static directory:

| Struts Source | Spring Boot Destination |
|---|---|
| `src/main/webapp/css/` | `src/main/resources/static/css/` |
| `src/main/webapp/js/` | `src/main/resources/static/js/` |
| `src/main/webapp/images/` | `src/main/resources/static/images/` |
| `src/main/webapp/fonts/` | `src/main/resources/static/fonts/` |
| `src/main/webapp/favicon.ico` | `src/main/resources/static/favicon.ico` |

Spring Boot serves `static/` resources automatically at the same URL paths. No servlet mapping required.

Update any hardcoded paths in CSS or JavaScript files that referenced the old webapp root.

### 5. i18n Message Bundle Migration

Move message properties files from Struts location to Spring Boot location:

| Struts | Spring Boot |
|---|---|
| `src/main/resources/ApplicationResources.properties` | `src/main/resources/messages.properties` |
| `src/main/resources/ApplicationResources_fr.properties` | `src/main/resources/messages_fr.properties` |

Configure Spring Boot message source:
```properties
spring.messages.basename=messages
spring.messages.encoding=UTF-8
spring.messages.cache-duration=3600
```

In Thymeleaf: `#{label.save}` resolves from `messages.properties`.

### 6. Error Pages

Create Spring Boot error pages:
```
src/main/resources/templates/error/
├── 404.html    # Not Found
├── 403.html    # Forbidden
└── 500.html    # Internal Server Error
```

```html
<!-- templates/error/404.html -->
<!DOCTYPE html>
<html lang="en" xmlns:th="http://www.thymeleaf.org">
<head><title>Page Not Found</title></head>
<body>
    <h1>404 — Page Not Found</h1>
    <p th:text="${message}">The requested resource was not found.</p>
    <a th:href="@{/}">Return to Home</a>
</body>
</html>
```

---

## Inputs

Read from `struts-app/` (read-only) and `docs/`:

| Path | Purpose |
|---|---|
| `docs/MIGRATION-INVENTORY.md` | View Inventory section — JSP files and view strategy per file |
| `struts-app/src/main/webapp/WEB-INF/jsp/{module}/` | JSP source files for the current module |
| `struts-app/src/main/webapp/WEB-INF/tiles-defs.xml` | Tiles layout definitions (if Tiles is used) |
| `struts-app/src/main/resources/ApplicationResources*.properties` | i18n message files |
| `struts-app/src/main/webapp/css/` | Static CSS assets |
| `struts-app/src/main/webapp/js/` | Static JS assets |
| `struts-app/src/main/webapp/images/` | Static image assets |
| `spring-boot-app/src/main/java/.../controller/{Module}Controller.java` | Verify view name alignment |

---

## Outputs

All files written to `spring-boot-app/`:

| Output Path | Description |
|---|---|
| `spring-boot-app/src/main/resources/templates/{module}/*.html` | Thymeleaf templates (Option A) |
| `spring-boot-app/src/main/resources/templates/layouts/default.html` | Base layout (if Tiles used) |
| `spring-boot-app/src/main/resources/templates/error/404.html` | 404 error page |
| `spring-boot-app/src/main/resources/templates/error/403.html` | 403 error page |
| `spring-boot-app/src/main/resources/templates/error/500.html` | 500 error page |
| `spring-boot-app/src/main/resources/static/css/` | Migrated CSS (copied from `struts-app/`) |
| `spring-boot-app/src/main/resources/static/js/` | Migrated JS (copied from `struts-app/`) |
| `spring-boot-app/src/main/resources/static/images/` | Migrated images (copied from `struts-app/`) |
| `spring-boot-app/src/main/resources/messages*.properties` | Migrated i18n message bundles |

For Option B (REST): No template files. Update controller class annotations in `spring-boot-app/` only.

---

## Constraints

### MUST NOT
- Mix strategies within a module (some views Thymeleaf, others REST)
- Delete any file inside `struts-app/`
- Modify any Java file in `spring-boot-app/controller/` (that is Code Transformation Agent's job)
- Modify business logic in any controller
- Change URL paths (those are set by the Code Transformation Agent)
- Add new CSS frameworks or JS libraries without inventory approval

### MUST
- Confirm the view strategy for each module before generating templates
- Use `th:action` (not `action`) on all Thymeleaf forms — ensures CSRF token injection
- Never disable CSRF for Thymeleaf form-based applications
- Set `spring.thymeleaf.cache=false` in dev profile
- Keep all JSP files in `struts-app/` intact until the Validation & Testing Agent signs off
- Mark superseded JSP files as "Superseded" in `docs/MIGRATION-INVENTORY.md`

---

## Examples

### Good: Form with CSRF Protection
```html
<form th:action="@{/persons}" th:object="${personForm}" method="post">
    <input type="text" th:field="*{firstName}" />
    <span th:errors="*{firstName}" class="error"></span>
    <button type="submit">Save</button>
</form>
```
Using `th:action` ensures Spring Security's CSRF token is injected automatically.

### Bad: Form Without CSRF
```html
<form action="/persons" method="post">
    <input type="text" name="firstName" />
    <button type="submit">Save</button>
</form>
```
Missing `th:action`. Spring Security CSRF protection will reject this form POST with 403.

### Good: URL Generation
```html
<a th:href="@{/persons/{id}/edit(id=${person.id})}">Edit</a>
```

### Bad: Hardcoded URL with Struts Suffix
```html
<a href="/admin/person-input.action?id=${person.id}">Edit</a>
```
Struts `.action` suffix, hardcoded URL, raw JSP EL. None of these work in Spring Boot.

---

## Edge Cases

### AJAX Calls to Struts Actions in JavaScript
If JSP files contain JavaScript that makes AJAX calls to `.action` URLs:
- Document every AJAX endpoint in `URL-MAPPING.md`
- Update the URL in the JavaScript to the new Spring Boot URL
- For REST strategy: the controller method already returns JSON, so the AJAX call works
- For Thymeleaf strategy: either keep the AJAX call pointing to a new REST endpoint, or remove AJAX and use server-rendered form submission

### Tiles with Multiple Content Regions
If Tiles defines multiple regions (header, sidebar, content, footer):
```html
<!-- Thymeleaf layout with fragments -->
<html layout:decorate="~{layouts/default}">
<body>
    <aside layout:fragment="sidebar"><!-- sidebar content --></aside>
    <main layout:fragment="content"><!-- main content --></main>
</body>
</html>
```
Add the `thymeleaf-layout-dialect` dependency to `pom.xml`.

### Custom JSP Taglibs
If the JSP uses custom project-specific taglibs (not Struts tags):
- Identify the taglib implementation class
- Implement equivalent Thymeleaf dialect or use a Thymeleaf utility class
- Document as a risk in the migration inventory

---

## Definition of Done
- [ ] All JSPs from `struts-app/WEB-INF/jsp/{module}/` converted to `spring-boot-app/resources/templates/{module}/` OR controllers in `spring-boot-app/` converted to @RestController
- [ ] All Struts taglib usages replaced with Thymeleaf equivalents (no `<s:` tags in any template)
- [ ] All forms use `th:action` (CSRF protection active)
- [ ] All Tiles layouts converted to Thymeleaf layout dialect (if applicable)
- [ ] Static assets copied to `spring-boot-app/src/main/resources/static/`
- [ ] i18n message bundles migrated to `spring-boot-app/src/main/resources/messages*.properties`
- [ ] Error pages (404, 403, 500) created in `spring-boot-app/resources/templates/error/`
- [ ] All UI flows tested end-to-end by the Validation & Testing Agent
- [ ] Superseded JSP files marked in `docs/MIGRATION-INVENTORY.md`
- [ ] No file deleted from `struts-app/`
