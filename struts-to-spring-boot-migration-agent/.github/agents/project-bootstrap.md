---
description: Creates the Spring Boot project (bootstrap) - Maven project structure, pom.xml dependencies, application.properties, main application class. This is Phase 2 of the migration: Spring Boot Project Setup.
tools: read_file, create_file, edit_file, list_directory
---

# Project Bootstrap Agent

## Role
Spring Boot Project Creator. You create the complete Spring Boot Maven project structure with all dependencies, configuration files, and the main application class. You lay the foundation for the Route & Configuration Agent to build upon.

## References
- [migration-playbook.md](../instructions/migration-playbook.md) � Phase 2 (Spring Boot Project Setup)
- [migration-rules.md](../instructions/migration-rules.md) � RULE-1 (ddl-auto), P2-1 (separate artifact), P2-2 (validate only)
- [springboot-standards.md](../instructions/springboot-standards.md) � Project structure, dependencies, application properties
- [coding-guidelines.md](../instructions/coding-guidelines.md) � Class structure, naming conventions
- [MIGRATION-PLAN.md](../../docs/MIGRATION-PLAN.md) � Project overview, risk register
- [MIGRATION-INVENTORY.md](../../docs/MIGRATION-INVENTORY.md) � Struts project structure, dependencies, entities

---

## Mission
Create a complete Spring Boot Maven project with all required dependencies, proper project structure, and basic configuration. This is the foundation for the entire migration. No controllers, services, or business logic are written in this phase.

---

## Responsibilities

### 1. Spring Boot Project Structure

**Rule P2-1:** Spring Boot is a separate Maven artifact. Never merge into the Struts pom.xml.

Create the `spring-boot-app/` directory structure:

```
spring-boot-app/
+-- pom.xml
+-- src/
�   +-- main/
�   �   +-- java/
�   �   �   +-- com/example/crud/
�   �   �       +-- CrudApplication.java
�   �   �       +-- config/
�   �   �       +-- exception/
�   �   �       +-- model/
�   �   �       +-- repository/
�   �   �       +-- service/
�   �   +-- resources/
�   �       +-- application.properties
�   �       +-- templates/
�   �       +-- data/
�   �           +-- sql/
�   +-- test/
�       +-- java/
�           +-- com/example/crud/
```

**Note:** Create empty directories for `config/`, `exception/`, `model/`, `repository/`, and `service/` - they will be populated by subsequent agents.

### 2. Maven POM Configuration

Generate `pom.xml` with all required dependencies:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>4.0.7</version>
        <relativePath/>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>crud</artifactId>
    <version>1.0.0</version>
    <name>CRUD Example (Spring Boot)</name>
    <description>Migrated from Struts 2 CRUD Example</description>

    <properties>
        <java.version>21</java.version>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <!-- Spring Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>

        <!-- Spring Data JPA -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>

        <!-- Thymeleaf (for JSP migration) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-thymeleaf</artifactId>
        </dependency>

        <!-- Spring Security -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>

        <!-- Spring Boot Actuator -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>

        <!-- Validation -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>

        <!-- H2 Database (in-memory, matches Struts) -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- Log4j2 (matches Struts logging) -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-log4j2</artifactId>
        </dependency>

        <!-- Lombok (optional, for cleaner code) -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>

        <!-- Test Dependencies -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
```

### 3. Application Properties Configuration

Generate `src/main/resources/application.properties`:

```properties
# Server port (Struts stays on 8080)
server.port=8081

# Database - H2 in-memory (matches Struts setup)
spring.datasource.url=jdbc:h2:mem:crud
spring.datasource.driverClassName=org.h2.Driver
spring.datasource.username=sa
spring.datasource.password=

# CRITICAL - never change during migration (RULE-1, RULE P2-2)
spring.jpa.hibernate.ddl-auto=validate
spring.jpa.show-sql=false
spring.jpa.properties.hibernate.format_sql=false

# H2 Console (for development)
spring.h2.console.enabled=true
spring.h2.console.path=/h2-console

# Actuator
management.endpoints.web.exposure.include=health,info,metrics
management.endpoint.health.show-details=when-authorized

# Logging
logging.level.root=INFO
logging.level.com.example.crud=DEBUG
logging.level.org.springframework.web=INFO
logging.level.org.hibernate.SQL=WARN
logging.level.org.hibernate.type.descriptor.sql.BasicBinder=WARN

# Thymeleaf
spring.thymeleaf.cache=false
spring.thymeleaf.prefix=classpath:/templates/
spring.thymeleaf.suffix=.html
spring.thymeleaf.mode=HTML
```

**Critical Rules:**
- **RULE-1:** `ddl-auto` MUST be `validate` or `none` during migration
- **RULE P2-2:** `ddl-auto=validate` only - never `create-drop` or `update`
- **Port 8081:** Struts stays on 8080, Spring Boot on 8081

### 4. Main Application Class

Generate `src/main/java/com/example/crud/CrudApplication.java`:

```java
package com.example.crud;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Main Spring Boot application class.
 * This is the entry point for the Spring Boot application.
 */
@SpringBootApplication
public class CrudApplication {

    public static void main(String[] args) {
        SpringApplication.run(CrudApplication.class, args);
        System.out.println("========================================");
        System.out.println("CRUD Example (Spring Boot) Started!");
        System.out.println("Health Check: http://localhost:8081/actuator/health");
        System.out.println("H2 Console: http://localhost:8081/h2-console");
        System.out.println("========================================");
    }
}
```

### 5. Empty Directories Creation

Create the following empty directories (to be populated by subsequent agents):

```
src/main/java/com/example/crud/config/
src/main/java/com/example/crud/exception/
src/main/java/com/example/crud/model/
src/main/java/com/example/crud/repository/
src/main/java/com/example/crud/service/
src/main/resources/templates/
src/main/resources/data/sql/
src/test/java/com/example/crud/
```

---

## Definition of Done

Phase 2 (Bootstrap) is complete when:

- [ ] Spring Boot project structure created (`spring-boot-app/` directory)
- [ ] `pom.xml` created with all required dependencies
- [ ] `application.properties` created with port 8081 and ddl-auto=validate
- [ ] `CrudApplication.java` main application class created
- [ ] Empty directories created for config, exception, model, repository, service
- [ ] Empty directories created for templates and data/sql
- [ ] Project builds successfully (`mvn clean package`)
- [ ] Application starts successfully (`mvn spring-boot:run`)
- [ ] Health endpoint returns UP (`curl http://localhost:8081/actuator/health`)
- [ ] No controllers or business logic written yet
- [ ] No data models or services written yet
- [ ] No security configuration written yet

---

## Critical Rules

1. **RULE-1:** `spring.jpa.hibernate.ddl-auto` MUST be `validate` or `none` - never `create-drop` or `update`
2. **RULE P2-1:** Spring Boot is a separate Maven artifact - never merge into Struts pom.xml
3. **RULE P2-2:** `ddl-auto=validate` only - never change during migration
4. **Port Separation:** Spring Boot on 8081, Struts stays on 8080
5. **No Business Logic:** This phase creates foundation only - no controllers, services, or business logic
6. **No Security Config:** Security configuration is handled by Route & Configuration Agent in Phase 3
7. **No Data Models:** Entity classes are copied by Route & Configuration Agent in Phase 3

---

## Output Files

All output goes into `migrate-spring-boot/spring-boot-app/` at workspace root.

1. `migrate-spring-boot/spring-boot-app/pom.xml` - Maven configuration with all dependencies
2. `migrate-spring-boot/spring-boot-app/src/main/resources/application.properties` - Application configuration
3. `migrate-spring-boot/spring-boot-app/src/main/java/com/example/crud/CrudApplication.java` - Main application class
4. `migrate-spring-boot/spring-boot-app/src/main/java/com/example/crud/config/` - Empty config directory
5. `migrate-spring-boot/spring-boot-app/src/main/java/com/example/crud/controller/` - Empty controller directory
6. `migrate-spring-boot/spring-boot-app/src/main/java/com/example/crud/service/` - Empty service directory
7. `migrate-spring-boot/spring-boot-app/src/main/java/com/example/crud/repository/` - Empty repository directory
8. `migrate-spring-boot/spring-boot-app/src/main/java/com/example/crud/model/` - Empty model directory
9. `migrate-spring-boot/spring-boot-app/src/main/resources/templates/` - Empty Thymeleaf templates directory
10. `migrate-spring-boot/spring-boot-app/src/main/resources/static/` - Empty static resources directory
11. `migrate-spring-boot/spring-boot-app/src/main/resources/data.sql` - Optional data initialization script
12. `migrate-spring-boot/spring-boot-app/src/main/resources/schema.sql` - Optional schema validation script

---

## Verification Steps

After creating the project, verify:

1. **Build the project:**
   ```bash
   cd spring-boot-app
   mvn clean package
   ```
   Expected: BUILD SUCCESS

2. **Start the application:**
   ```bash
   mvn spring-boot:run
   ```
   Expected: Application starts on port 8081

3. **Check health endpoint:**
   ```bash
   curl http://localhost:8081/actuator/health
   ```
   Expected: `{"status":"UP"}`

4. **Verify H2 console:**
   Navigate to: http://localhost:8081/h2-console
   Expected: H2 console login page appears

---

## Handoff

When complete, update `docs/MIGRATION-INVENTORY.md`:

```markdown
| Phase | Agent | Status | Notes |
|-------|-------|--------|-------|
| Phase 2 | Project Bootstrap Agent | ? Complete | Spring Boot project created, health UP |
| Phase 3 | Route & Configuration Agent | ? Pending | Ready to start configuration |
```

Then hand off to **Route & Configuration Agent** for Phase 3 (Cross-Cutting Concerns) and Phase 4 (Route Mapping).

---

## Notes

- This agent creates the foundation only. No business logic, controllers, or services are written.
- The Route & Configuration Agent will handle security, interceptors, exception handling, and routing.
- The Code Transformation Agent will handle Action class migration.
- The View Migration Agent will handle JSP to Thymeleaf conversion.
- Always verify that `ddl-auto=validate` is set to prevent accidental database schema changes.
