---
applyTo: "**"
---

# Coding Guidelines

> **Scope:** Java coding standards for all code generated or transformed during the Struts-to-Spring Boot migration.
> Apply these guidelines to every `.java` file produced.

---

## General Principles

- **Preserve behavior first.** Migrated code must be functionally equivalent to the original Struts code. Refactoring and improvement come after verification.
- **No gold-plating.** Do not add features, abstractions, or patterns beyond what the migration requires.
- **Readability over cleverness.** Prefer explicit over implicit. Prefer simple over complex.
- **Minimal diff.** Field names, method names, and business logic must not change during migration unless required by Spring conventions.

---

## Naming Conventions

### Classes
| Type | Convention | Example |
|---|---|---|
| Controller | `{Domain}Controller` | `PersonController` |
| Service interface | `{Domain}Service` | `PersonService` |
| Service implementation | `{Domain}ServiceImpl` | `PersonServiceImpl` |
| Repository | `{Domain}Repository` | `PersonRepository` |
| Entity | `{Domain}` | `Person` |
| Request DTO | `{Domain}Request` | `PersonRequest` |
| Response DTO | `{Domain}Response` | `PersonResponse` |
| Form DTO (Thymeleaf) | `{Domain}Form` | `PersonForm` |
| Exception | `{Context}Exception` | `ResourceNotFoundException` |
| Filter | `{Purpose}Filter` | `RequestLoggingFilter` |
| Config class | `{Purpose}Config` | `SecurityConfig` |

### Methods
- Controllers: HTTP verb prefix — `list()`, `getById()`, `create()`, `update()`, `delete()`
- Services: business verb — `getAll()`, `getById()`, `save()`, `update()`, `delete()`
- Repositories: Spring Data naming — `findByEmail()`, `findAllByStatus()`

### Fields
- Match the original Struts Action field names exactly unless forced by Java conventions
- No abbreviations: `firstName` not `fn`, `personRepository` not `repo`
- Boolean fields: `is` prefix — `isActive`, `isEnabled`

---

## Class Structure Order

Follow this declaration order within every class:

1. Static constants (`public static final`)
2. Instance fields (private, in dependency-injection order)
3. Constructor(s)
4. Public methods
5. Protected methods
6. Private helper methods
7. Inner classes / enums (if necessary)

---

## Imports

- No wildcard imports (`import java.util.*` → forbidden)
- Group imports: Java standard → third-party → project internal
- Remove all Struts imports from migrated files:
  - `com.opensymphony.xwork2.*`
  - `org.apache.struts2.*`
  - `com.opensymphony.xwork2.ActionSupport`
  - `com.opensymphony.xwork2.Preparable`
  - `org.apache.struts2.interceptor.*`

---

## Entity Rules

```java
@Entity
@Table(name = "person")  // Match existing table name exactly
public class Person {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "first_name", nullable = false, length = 100)  // Match existing column name
    private String firstName;

    @Column(name = "email", unique = true, nullable = false)
    private String email;

    // JPA requires no-arg constructor
    protected Person() {}

    // Constructor for creating new instances
    public Person(String firstName, String email) {
        this.firstName = firstName;
        this.email = email;
    }

    // Getters — no setters on entities (use constructor or builder)
    public Long getId() { return id; }
    public String getFirstName() { return firstName; }
    public String getEmail() { return email; }
}
```

Rules:
- Column names must match the existing database schema exactly — do not rename
- Do not add business logic to entities
- Do not put `@JsonIgnore` or `@JsonProperty` on entity fields — use DTOs
- Do not use `@Data` (Lombok) on JPA entities — it breaks `equals()`/`hashCode()` with lazy loading

---

## DTO Rules

```java
// Request DTO — inbound validation
public class PersonRequest {

    @NotBlank(message = "First name is required")
    @Size(max = 100, message = "First name must not exceed 100 characters")
    private String firstName;

    @NotBlank(message = "Email is required")
    @Email(message = "Email must be a valid address")
    private String email;

    // Getters and setters required for @ModelAttribute binding
    public String getFirstName() { return firstName; }
    public void setFirstName(String firstName) { this.firstName = firstName; }
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
}

// Response DTO — outbound data
public class PersonResponse {
    private final Long id;
    private final String firstName;
    private final String email;

    public PersonResponse(Long id, String firstName, String email) {
        this.id = id;
        this.firstName = firstName;
        this.email = email;
    }

    // Getters only — immutable
    public Long getId() { return id; }
    public String getFirstName() { return firstName; }
    public String getEmail() { return email; }
}
```

---

## Transaction Rules

```java
@Service
public class PersonServiceImpl implements PersonService {

    @Override
    @Transactional(readOnly = true)     // Read-only for queries
    public List<PersonResponse> getAll() {
        return personRepository.findAll().stream()
            .map(this::toResponse)
            .collect(Collectors.toList());
    }

    @Override
    @Transactional                       // Write for mutations
    public PersonResponse save(PersonRequest request) {
        Person person = new Person(request.getFirstName(), request.getEmail());
        Person saved = personRepository.save(person);
        return toResponse(saved);
    }

    private PersonResponse toResponse(Person person) {
        return new PersonResponse(person.getId(), person.getFirstName(), person.getEmail());
    }
}
```

Rules:
- `@Transactional(readOnly = true)` on all query methods
- `@Transactional` (default) on all write methods
- Never put `@Transactional` on controller methods
- Transaction scope must match the original Struts behavior

---

## Logging

Use SLF4J (provided by Spring Boot starter):

```java
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class PersonServiceImpl implements PersonService {
    private static final Logger log = LoggerFactory.getLogger(PersonServiceImpl.class);

    public PersonResponse save(PersonRequest request) {
        log.debug("Saving person with email: {}", request.getEmail());
        // ... implementation
        log.info("Person saved with id: {}", saved.getId());
        return toResponse(saved);
    }
}
```

Log level guidelines:
- `TRACE` — very detailed flow tracing (disabled in production)
- `DEBUG` — method entry/exit, parameter values
- `INFO` — significant business events (entity created, user logged in)
- `WARN` — recoverable unexpected conditions
- `ERROR` — exceptions that require attention; always include the exception object

---

## Exception Handling Rules

### Custom Exceptions
```java
public class ResourceNotFoundException extends RuntimeException {
    public ResourceNotFoundException(String resourceName, Long id) {
        super(String.format("%s not found with id: %d", resourceName, id));
    }
}
```

Rules:
- Use unchecked exceptions (`RuntimeException` subclasses) for business errors
- Map every Struts `<exception-mapping>` to a specific `@ExceptionHandler` in `GlobalExceptionHandler`
- Never catch `Exception` and swallow it silently — always log or rethrow
- Never use `e.printStackTrace()` — use `log.error("message", e)`

---

## Forbidden Patterns

| Pattern | Why Forbidden |
|---|---|
| `System.out.println(...)` | Use SLF4J logging |
| `e.printStackTrace()` | Use `log.error("msg", e)` |
| `new ServiceClass()` inside Spring bean | Bypasses Spring DI |
| Catching `Exception` and returning `null` | Masks errors |
| Business logic in controller | Violates separation of concerns |
| Database query in controller | Violates layering |
| JPA entity in HTTP response JSON | Exposes internal model; use DTO |
| Wildcard imports | Reduces readability |
| Struts imports in Spring Boot files | Migration artifact |
| `@Transactional` on controller methods | Wrong layer |
| `synchronized` blocks without analysis | Concurrency issue |
| Magic numbers/strings without constants | Reduces readability |

---

## Migration-Specific Rules

### Preserving Business Logic
- Copy business logic verbatim from Struts `execute()`, `save()`, `list()`, etc. into the corresponding service method
- Do not simplify, optimize, or refactor business logic during the migration pass
- Add a `// Migrated from: ClassName.methodName()` comment only when the origin is non-obvious
- If you find a bug in the original logic, flag it in the migration inventory — do not fix it during migration

### Field Name Preservation
- Struts Action field names become DTO field names without change
- If a field is named `firstName` in Struts, the DTO field must also be `firstName`
- Column names in JPA `@Column` must match the existing database column names exactly

### Method Ordering
- Preserve the logical grouping from the Struts Action class
- Group CRUD operations: list → getById → create → update → delete
