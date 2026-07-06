---
applyTo: "**"
---

# Testing Guidelines

> **Scope:** Standards for all tests generated during the Struts-to-Spring Boot migration.
> Tests are not written at the end of migration — they are written alongside each migrated module and must pass before any traffic switch.

---

## Test Pyramid

Each migrated module must produce tests at three levels:

```
                    ▲
                   /|\
                  / | \
           Manual/  |  \
         Smoke Tests|   \
          (user      |    \
          journeys)  |     \
                     |      \
         ─────────────────────
         Integration Tests
         @SpringBootTest + TestRestTemplate
         (full stack, shared DB)
         ─────────────────────────────────
         Controller Slice Tests
         @SpringBootTest + @AutoConfigureMockMvc (HTTP layer)
         ─────────────────────────────────────────
         Unit Tests
         Plain JUnit, Mockito (no Spring context)
         ─────────────────────────────────────────────
```

Rule: Traffic may not be switched for a module until all three test levels pass.

---

## Unit Tests

### Scope
- Service layer methods
- Utility/helper classes
- Custom validators
- DTO transformations

### Setup
```java
@ExtendWith(MockitoExtension.class)
class PersonServiceImplTest {

    @Mock
    private PersonRepository personRepository;

    @InjectMocks
    private PersonServiceImpl personService;

    @Test
    void getAll_returnsAllPersonsAsDTOs() {
        // Arrange
        List<Person> entities = List.of(
            new Person("Alice", "alice@example.com"),
            new Person("Bob", "bob@example.com")
        );
        when(personRepository.findAll()).thenReturn(entities);

        // Act
        List<PersonResponse> result = personService.getAll();

        // Assert
        assertThat(result).hasSize(2);
        assertThat(result.get(0).getFirstName()).isEqualTo("Alice");
        verify(personRepository, times(1)).findAll();
    }

    @Test
    void getById_whenNotFound_throwsResourceNotFoundException() {
        when(personRepository.findById(99L)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> personService.getById(99L))
            .isInstanceOf(ResourceNotFoundException.class)
            .hasMessageContaining("Person not found with id: 99");
    }
}
```

### Rules
- No Spring context loading — tests must be fast (< 100ms each)
- Mock all dependencies with Mockito `@Mock`
- One assertion group per test method
- Test both the happy path and all error paths
- Name tests: `methodName_condition_expectedBehavior`

---

## Controller Slice Tests

### Scope
- HTTP layer: request mapping, response codes, JSON serialization, validation
- Does NOT test business logic or database

### Setup
```java
@SpringBootTest
@AutoConfigureMockMvc
class PersonControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private PersonService personService;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    @WithMockUser(roles = "USER")
    void list_returnsOkWithPersonList() throws Exception {
        List<PersonResponse> persons = List.of(
            new PersonResponse(1L, "Alice", "alice@example.com")
        );
        when(personService.getAll()).thenReturn(persons);

        mockMvc.perform(get("/api/persons")
                .contentType(MediaType.APPLICATION_JSON))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(1)))
            .andExpect(jsonPath("$[0].firstName").value("Alice"));
    }

    @Test
    @WithMockUser(roles = "USER")
    void create_withInvalidEmail_returnsBadRequest() throws Exception {
        PersonRequest badRequest = new PersonRequest();
        badRequest.setFirstName("Alice");
        badRequest.setEmail("not-an-email");

        mockMvc.perform(post("/api/persons")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(badRequest)))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.errors.email").exists());
    }

    @Test
    void list_whenUnauthenticated_returns401() throws Exception {
        mockMvc.perform(get("/api/persons"))
            .andExpect(status().isUnauthorized());
    }
}
```

### Rules
- Use `@SpringBootTest` + `@AutoConfigureMockMvc` for controller slice tests
- Mock all services with `@MockitoBean`
- Test every HTTP status code: 200, 201, 400, 401, 403, 404, 500
- Test security: both authenticated and unauthenticated requests
- Test validation: submit invalid input and assert 400 + error structure

---

## Integration Tests

### Scope
- Full application stack
- Runs against the shared database (not H2 in-memory)
- Tests that the migrated module produces identical outputs to the Struts original

### Setup
```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@TestPropertySource(properties = {
    "spring.jpa.hibernate.ddl-auto=validate",
    "spring.datasource.url=jdbc:mysql://localhost:3306/test_db"
})
class PersonIntegrationTest {

    @Autowired
    private TestRestTemplate restTemplate;

    @Test
    void createAndRetrievePerson_fullRoundTrip() {
        PersonRequest request = new PersonRequest();
        request.setFirstName("Integration Test User");
        request.setEmail("integration@example.com");

        // Create
        ResponseEntity<PersonResponse> createResponse =
            restTemplate.withBasicAuth("user", "password")
                .postForEntity("/api/persons", request, PersonResponse.class);

        assertThat(createResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(createResponse.getBody()).isNotNull();
        Long id = createResponse.getBody().getId();

        // Retrieve
        ResponseEntity<PersonResponse> getResponse =
            restTemplate.withBasicAuth("user", "password")
                .getForEntity("/api/persons/" + id, PersonResponse.class);

        assertThat(getResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(getResponse.getBody().getFirstName()).isEqualTo("Integration Test User");
    }
}
```

### Rules
- Must use `spring.jpa.hibernate.ddl-auto=validate` — never `create-drop` in tests
- Test against the shared database schema, not H2
- Every user journey from the Struts migration inventory must have a corresponding integration test
- Tests must be independent — use `@Transactional` + rollback, or explicit cleanup

---

## Parallel Verification Tests

For every migrated endpoint, run both the Struts and Spring Boot versions with identical inputs and verify outputs match:

```bash
# Step 1: Capture Struts response
curl -u user:password http://localhost:8080/admin/persons/list.action \
  -H "Accept: application/json" > struts_response.json

# Step 2: Capture Spring Boot response  
curl -u user:password http://localhost:8081/api/persons \
  -H "Accept: application/json" > spring_response.json

# Step 3: Normalize and compare (field order may differ)
python -c "
import json, sys
s = json.load(open('struts_response.json'))
b = json.load(open('spring_response.json'))
# Compare relevant fields
assert len(s) == len(b), 'Count mismatch'
print('PASS: Responses match')
"
```

This verification is mandatory before switching traffic for any module.

---

## Rollback Testing

Before going live with any module switch, verify the rollback procedure:

1. Switch a module's traffic to Spring Boot (nginx config change)
2. Make a test request → verify Spring Boot is serving it
3. Revert the nginx config change
4. Make a test request → verify Struts is serving it again
5. Time the whole procedure — must complete in under 5 minutes

Document the rollback time in the module's completion report.

---

## Test Coverage Requirements

| Layer | Minimum Coverage |
|---|---|
| Service methods (business logic) | 90% line coverage |
| Controller endpoints | 100% endpoint coverage (all HTTP methods + status codes) |
| Integration tests | 100% of user journeys from migration inventory |
| Security tests | 100% of URL patterns (authenticated + unauthenticated) |
| Validation tests | All `@Valid` constraints on all Request DTOs |

---

## Testing Anti-Patterns

| Anti-Pattern | Problem | Correct Approach |
|---|---|---|
| `@WebMvcTest` for controller tests | Compatibility issues in Spring Boot 4.x | Use `@SpringBootTest` + `@AutoConfigureMockMvc` for controller layer |
| H2 in-memory DB for integration tests | Masks schema differences | Use the shared MySQL/PostgreSQL DB |
| `ddl-auto=create-drop` in test config | Destroys shared DB data | Use `validate` always |
| Tests with no assertions | Meaningless | Every test must assert something |
| One test per class | Insufficient coverage | Test happy path + all error paths |
| Skipping security tests | Unauthenticated endpoint in prod | Always test 401/403 |
| Ignoring test failures to meet deadline | Technical debt | Fix failures before switching traffic |
| Mocking the database in integration tests | Misses real behavior | Use the real database |
| Testing implementation details | Brittle tests | Test observable behavior |

---

## Test File Naming

```
src/test/java/com/example/app/
├── service/
│   └── PersonServiceImplTest.java          # Unit test for service
├── controller/
│   └── PersonControllerTest.java           # @SpringBootTest + @AutoConfigureMockMvc controller slice
└── integration/
    ├── PersonIntegrationTest.java           # Full stack integration
    └── SecurityIntegrationTest.java         # Security rules integration test
```

---

## Definition of Done for a Module's Tests

- [ ] Unit tests cover all service methods (happy path + error paths)
- [ ] Controller slice tests cover all endpoints and HTTP status codes
- [ ] Controller slice tests verify 401/403 for unauthenticated access
- [ ] Integration tests cover all user journeys from the migration inventory
- [ ] Parallel verification: Spring Boot responses match Struts responses
- [ ] Rollback test completed and timed (< 5 minutes)
- [ ] All tests pass in CI pipeline
- [ ] Test coverage meets minimum thresholds
