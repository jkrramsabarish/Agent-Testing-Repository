---
applyTo: "**"
---

# Spring Boot Standards

> **Scope:** Enterprise-grade Spring Boot 3.x patterns that all generated code must follow.
> These standards apply to every file produced by any migration agent.

---

## Project Structure

```
src/
├── main/
│   ├── java/com/example/app/
│   │   ├── Application.java                  # @SpringBootApplication entry point
│   │   ├── config/                           # @Configuration classes only
│   │   │   ├── SecurityConfig.java
│   │   │   ├── WebMvcConfig.java
│   │   │   └── DataSourceConfig.java
│   │   ├── controller/                       # @RestController / @Controller
│   │   │   └── PersonController.java
│   │   ├── service/                          # @Service interfaces + implementations
│   │   │   ├── PersonService.java
│   │   │   └── impl/PersonServiceImpl.java
│   │   ├── repository/                       # @Repository / JPA repositories
│   │   │   └── PersonRepository.java
│   │   ├── entity/                           # @Entity classes
│   │   │   └── Person.java
│   │   ├── dto/                              # Request/Response DTOs (no JPA annotations)
│   │   │   ├── PersonRequest.java
│   │   │   └── PersonResponse.java
│   │   ├── exception/                        # Custom exceptions
│   │   │   ├── ResourceNotFoundException.java
│   │   │   └── GlobalExceptionHandler.java
│   │   └── filter/                           # OncePerRequestFilter implementations
│   │       └── RequestLoggingFilter.java
│   └── resources/
│       ├── application.properties
│       ├── application-dev.properties
│       ├── application-prod.properties
│       ├── static/                           # CSS, JS, images
│       │   ├── css/
│       │   ├── js/
│       │   └── images/
│       └── templates/                        # Thymeleaf templates
│           └── persons/
│               ├── list.html
│               └── edit.html
└── test/
    └── java/com/example/app/
        ├── controller/                       # @WebMvcTest tests
        ├── service/                          # Unit tests
        └── integration/                      # @SpringBootTest tests
```

---

## Layer Responsibilities

### Controller Layer (`@RestController` / `@Controller`)
- Handle HTTP request/response only
- Delegate all business logic to the service layer
- No database access directly
- No business rules in the controller
- Validate input using `@Valid` + `BindingResult`
- Return DTOs, not entities

### Service Layer (`@Service`)
- Contain all business logic
- Annotate data-modifying methods with `@Transactional`
- Define interfaces; implement in `impl/` package
- Never return JPA entities to the controller — convert to DTO

### Repository Layer (`@Repository`)
- Use Spring Data JPA `JpaRepository` as the default
- Custom queries use `@Query` with JPQL (not native SQL unless necessary)
- Never contain business logic

### Entity Layer (`@Entity`)
- Represent database tables
- No business logic
- No Jackson `@JsonIgnore` / `@JsonProperty` — use DTOs for serialization
- JPA-annotated field names must match existing column names exactly

### DTO Layer
- Separate `Request` DTOs (inbound) and `Response` DTOs (outbound)
- Use Bean Validation annotations on Request DTOs
- No JPA annotations on DTOs
- Use constructor injection or Lombok `@Value` / `@Builder` for immutability

---

## Dependency Injection

```java
// CORRECT — constructor injection (preferred)
@Service
public class PersonServiceImpl implements PersonService {
    private final PersonRepository personRepository;

    public PersonServiceImpl(PersonRepository personRepository) {
        this.personRepository = personRepository;
    }
}

// ACCEPTABLE — field injection (use only when constructor injection causes circular deps)
@Service
public class PersonServiceImpl implements PersonService {
    @Autowired
    private PersonRepository personRepository;
}

// FORBIDDEN — manual instantiation
@Service
public class PersonServiceImpl implements PersonService {
    private PersonRepository personRepository = new PersonRepositoryImpl(); // NEVER
}
```

---

## Controller Patterns

### REST Controller
```java
@RestController
@RequestMapping("/api/persons")
public class PersonController {

    private final PersonService personService;

    public PersonController(PersonService personService) {
        this.personService = personService;
    }

    @GetMapping
    public ResponseEntity<List<PersonResponse>> list() {
        return ResponseEntity.ok(personService.getAll());
    }

    @GetMapping("/{id}")
    public ResponseEntity<PersonResponse> getById(@PathVariable Long id) {
        return ResponseEntity.ok(personService.getById(id));
    }

    @PostMapping
    public ResponseEntity<PersonResponse> create(@Valid @RequestBody PersonRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(personService.create(request));
    }

    @PutMapping("/{id}")
    public ResponseEntity<PersonResponse> update(@PathVariable Long id,
                                                  @Valid @RequestBody PersonRequest request) {
        return ResponseEntity.ok(personService.update(id, request));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        personService.delete(id);
        return ResponseEntity.noContent().build();
    }
}
```

### Thymeleaf Controller
```java
@Controller
@RequestMapping("/persons")
public class PersonController {

    private final PersonService personService;

    public PersonController(PersonService personService) {
        this.personService = personService;
    }

    @GetMapping
    public String list(Model model) {
        model.addAttribute("persons", personService.getAll());
        return "persons/list";
    }

    @GetMapping("/new")
    public String newForm(Model model) {
        model.addAttribute("person", new PersonForm());
        return "persons/edit";
    }

    @PostMapping
    public String save(@Valid @ModelAttribute("person") PersonForm form,
                       BindingResult result,
                       RedirectAttributes ra) {
        if (result.hasErrors()) return "persons/edit";
        personService.save(form);
        ra.addFlashAttribute("message", "Saved successfully");
        return "redirect:/persons";
    }
}
```

---

## Security Configuration

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**", "/actuator/health").permitAll()
                .requestMatchers("/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .formLogin(Customizer.withDefaults())
            .csrf(csrf -> csrf.disable()); // Re-enable for Thymeleaf form-based apps
        return http.build();
    }
}
```

---

## Exception Handling

```java
@ControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(ResourceNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleNotFound(ResourceNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse(ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ValidationErrorResponse> handleValidation(
            MethodArgumentNotValidException ex) {
        Map<String, String> errors = new LinkedHashMap<>();
        ex.getBindingResult().getFieldErrors()
            .forEach(e -> errors.put(e.getField(), e.getDefaultMessage()));
        return ResponseEntity.badRequest().body(new ValidationErrorResponse(errors));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneral(Exception ex) {
        log.error("Unhandled exception", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse("Internal server error"));
    }
}
```

---

## application.properties Required Settings

```properties
# Server
server.port=8081

# Database — CRITICAL during migration
spring.datasource.url=jdbc:mysql://localhost:3306/existing_db
spring.datasource.username=app_user
spring.datasource.password=app_password
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver

# JPA — NEVER change during migration
spring.jpa.hibernate.ddl-auto=validate
spring.jpa.show-sql=false
spring.jpa.properties.hibernate.format_sql=true

# Actuator
management.endpoints.web.exposure.include=health,metrics,info
management.endpoint.health.show-details=when-authorized

# Thymeleaf (if applicable)
spring.thymeleaf.cache=false
spring.thymeleaf.prefix=classpath:/templates/
spring.thymeleaf.suffix=.html
```

---

## Annotation Quick Reference

| Purpose | Annotation | Layer |
|---|---|---|
| Entry point | `@SpringBootApplication` | Application class |
| REST controller | `@RestController` | Controller |
| View controller | `@Controller` | Controller |
| Route prefix | `@RequestMapping` | Controller class |
| GET handler | `@GetMapping` | Controller method |
| POST handler | `@PostMapping` | Controller method |
| PUT handler | `@PutMapping` | Controller method |
| DELETE handler | `@DeleteMapping` | Controller method |
| Path variable | `@PathVariable` | Method parameter |
| Request body | `@RequestBody` | Method parameter |
| Form binding | `@ModelAttribute` | Method parameter |
| Validate input | `@Valid` | Method parameter |
| Business service | `@Service` | Service class |
| Inject dependency | `@Autowired` (or constructor) | Service/Controller |
| Wrap in transaction | `@Transactional` | Service method |
| Data repository | `@Repository` | Repository interface |
| Database entity | `@Entity` | Entity class |
| Configuration | `@Configuration` | Config class |
| Security config | `@EnableWebSecurity` | Config class |
| Global exceptions | `@ControllerAdvice` | Exception handler |
| Exception handler | `@ExceptionHandler` | Handler method |
| Pre-request hook | `@ModelAttribute` | Controller method |
| Session binding | `@SessionAttributes` | Controller class |

---

## Anti-Patterns

| Anti-Pattern | Correct Approach |
|---|---|
| Business logic in controller | Move to `@Service` |
| JPA entity in HTTP response | Return DTO instead |
| `new ServiceClass()` inside Spring bean | Use `@Autowired` injection |
| `@Transactional` on controller method | Move to service method |
| Catching and swallowing all exceptions | Use `@ControllerAdvice` |
| `ddl-auto=create-drop` or `update` | Use `validate` during migration |
| Hardcoded credentials in source | Use `application.properties` + env vars |
| Native SQL queries everywhere | Use JPQL or Spring Data methods first |
| Returning `null` from controller | Return `ResponseEntity.notFound().build()` |
| Direct `HttpSession` manipulation in service | Keep session access in controller only |
