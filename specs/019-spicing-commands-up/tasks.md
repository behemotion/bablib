# Tasks: Context-Aware Command Enhancement

**Input**: Design documents from `/Users/alexandr/Repository/local-bablib/specs/019-spicing-commands-up/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

## Execution Flow (main)
```
1. Load plan.md from feature directory ✓
   → Extract: Python 3.13+, Click, Rich, Pydantic v2, FastAPI, pytest
2. Load optional design documents ✓:
   → data-model.md: 5 entities → 5 model tasks
   → contracts/: CLI + MCP contracts → 12 contract test tasks
   → quickstart.md: 4 user scenarios → 4 integration test tasks
3. Generate tasks by category:
   → Setup: project structure, dependencies, database migration
   → Tests: contract tests, integration tests (TDD approach)
   → Core: models, services, CLI enhancements, wizards
   → Integration: MCP endpoints, flag standardization
   → Polish: unit tests, performance validation, documentation
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph and parallel execution examples
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
**Single project structure** (from plan.md):
- Models: `src/models/`
- Services: `src/services/`
- CLI: `src/cli/`
- Logic: `src/logic/`
- Tests: `tests/contract/`, `tests/integration/`, `tests/unit/`

## Phase 3.1: Setup

- [X] T001 Create database migration for new tables (command_contexts, wizard_states, flag_definitions)
- [X] T002 Add configuration_state JSON columns to existing shelves/boxes/mcp_configurations tables
- [X] T003 [P] Install additional dependencies: rich, click enhancements for context-aware features
- [X] T004 [P] Configure pytest fixtures for wizard testing in tests/conftest.py

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests - Data Models
- [X] T005 [P] Contract test CommandContext model validation in tests/contract/test_command_context_model.py
- [X] T006 [P] Contract test WizardState model validation in tests/contract/test_wizard_state_model.py
- [X] T007 [P] Contract test ConfigurationState model validation in tests/contract/test_configuration_state_model.py
- [X] T008 [P] Contract test FlagDefinition model validation in tests/contract/test_flag_definition_model.py
- [X] T009 [P] Contract test WizardStep model validation in tests/contract/test_wizard_step_model.py

### Contract Tests - CLI Commands
- [X] T010 [P] Contract test enhanced shelf command behavior in tests/contract/test_shelf_command_enhanced.py
- [X] T011 [P] Contract test enhanced box command behavior in tests/contract/test_box_command_enhanced.py
- [X] T012 [P] Contract test enhanced fill command routing in tests/contract/test_fill_command_enhanced.py
- [X] T013 [P] Contract test enhanced serve command with wizards in tests/contract/test_serve_command_enhanced.py

### Contract Tests - MCP Endpoints
- [X] T014 [P] Contract test /context/shelf/{name} endpoint in tests/contract/test_mcp_context_shelf.py
- [X] T015 [P] Contract test /context/box/{name} endpoint in tests/contract/test_mcp_context_box.py
- [X] T016 [P] Contract test /admin/wizards/start endpoint in tests/contract/test_mcp_wizard_start.py
- [X] T017 [P] Contract test /admin/context/create-shelf endpoint in tests/contract/test_mcp_admin_shelf.py
- [X] T018 [P] Contract test /admin/context/create-box endpoint in tests/contract/test_mcp_admin_box.py

### Integration Tests - User Scenarios
- [X] T019 [P] Integration test new user setup scenario including shelf-level fill prompting in tests/integration/test_new_user_setup.py
- [X] T020 [P] Integration test content filling by box type in tests/integration/test_content_filling_by_type.py
- [X] T021 [P] Integration test MCP server setup wizard in tests/integration/test_mcp_server_setup.py
- [X] T022 [P] Integration test flag consistency experience in tests/integration/test_flag_consistency.py

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Data Models
- [X] T023 [P] CommandContext model in src/models/command_context.py
- [X] T024 [P] WizardState model in src/models/wizard_state.py
- [X] T025 [P] ConfigurationState model in src/models/configuration_state.py
- [X] T026 [P] FlagDefinition model in src/models/flag_definition.py
- [X] T027 [P] WizardStep model in src/models/wizard_step.py

### Context Detection Services
- [X] T028 [P] ContextService for shelf/box existence checking in src/services/context_service.py
- [X] T029 [P] ContextCache for performance optimization in src/services/context_cache.py
- [X] T030 [P] StatusDisplayService for entity status logic in src/services/status_display_service.py
- [X] T031 [P] StatusDisplayFormatter for consistent entity status presentation in src/services/status_display_formatter.py

### Wizard Framework
- [X] T032 WizardOrchestrator for session management in src/logic/wizard/orchestrator.py
- [X] T033 ShelfWizard with step definitions in src/logic/wizard/shelf_wizard.py
- [X] T034 BoxWizard with type-aware configuration in src/logic/wizard/box_wizard.py
- [X] T035 McpWizard with server setup flow in src/logic/wizard/mcp_wizard.py
- [X] T036 [P] WizardValidator for input validation in src/logic/wizard/validator.py

### CLI Command Enhancements
- [X] T037 Enhance shelf command with context awareness in src/cli/commands/shelf.py
- [X] T038 Enhance box command with context awareness in src/cli/commands/box.py
- [X] T039 Enhance fill command with type-aware routing in src/cli/commands/fill.py
- [X] T040 Enhance serve command with wizard integration in src/cli/commands/serve.py

### Flag Standardization
- [X] T041 [P] FlagStandardizer service for consistency in src/services/flag_standardizer.py
- [X] T042 [P] CommandRouter for enhanced routing in src/services/command_router.py
- [X] T043 Apply flag standardization to all existing commands in src/cli/

## Phase 3.4: Integration

### MCP Server Extensions
- [X] T044 Add context endpoints to read-only MCP server in src/logic/mcp/endpoints/context.py
- [X] T045 Add wizard endpoints to admin MCP server in src/logic/mcp/endpoints/wizard.py
- [X] T046 Add flag definition endpoints in src/logic/mcp/endpoints/flags.py
- [X] T047 [P] MCP context response formatters in src/logic/mcp/formatters/context_formatter.py

### Database Integration
- [X] T048 Connect context services to database layer
- [X] T049 Implement wizard state persistence and cleanup
- [X] T050 Add configuration state management to existing entities

### Performance Optimization
- [X] T051 [P] Implement context cache with 5-minute TTL in src/services/context_cache.py
- [X] T052 [P] Optimize database queries for context detection
- [X] T053 [P] Add performance monitoring for wizard state management

## Phase 3.5: Polish

### Unit Tests
- [X] T054 [P] Unit tests for context detection logic in tests/unit/test_context_detection.py
- [X] T055 [P] Unit tests for wizard state transitions in tests/unit/test_wizard_transitions.py
- [X] T056 [P] Unit tests for flag standardization in tests/unit/test_flag_standardization.py

### Performance Validation
- [X] T057 [P] Performance tests for context detection (<500ms) in tests/performance/test_context_performance.py
- [X] T058 [P] Performance tests for wizard step transitions (<200ms) in tests/performance/test_wizard_performance.py
- [X] T059 [P] Memory usage tests for wizard sessions (<50MB) in tests/performance/test_memory_usage.py

### Vector Database Compatibility
- [X] T060 [P] Test context awareness with SQLite-vec backend in tests/integration/test_sqlite_vec_context.py
- [X] T061 [P] Test context awareness with Qdrant backend in tests/integration/test_qdrant_context.py

### Documentation and Validation
- [X] T062 [P] Update CLAUDE.md with context-aware command patterns
- [X] T063 [P] Create user documentation for setup wizards
- [X] T064 Run quickstart.md manual validation scenarios
- [X] T065 [P] Add error handling documentation for context failures

### Constitutional Performance Validation
- [X] T066 [P] Validate <30s complete setup requirement in tests/performance/test_setup_time.py
- [X] T067 [P] Validate <5s system validation requirement in tests/performance/test_system_validation.py

## Dependencies

### Setup Dependencies
- T001-T004 must complete before any other tasks

### TDD Dependencies (Critical Path)
- **All tests (T005-T022) MUST complete and FAIL before implementation (T023-T053)**
- Models (T023-T027) before services (T028-T031, T041-T042)
- Context services (T028-T031) before CLI enhancements (T037-T040)
- Wizard framework (T032-T036) before CLI wizard integration (T037-T040)
- Core functionality (T023-T043) before MCP extensions (T044-T047)

### Implementation Dependencies
- T023 (CommandContext) blocks T028, T037, T038
- T024 (WizardState) blocks T032, T033, T034, T035
- T025 (ConfigurationState) blocks T030, T048, T050
- T032 (WizardOrchestrator) blocks T033, T034, T035, T045
- T037-T040 (CLI enhancements) blocks T048
- T044-T047 (MCP endpoints) blocks T061

### Critical Constitutional Dependencies
- T066 (setup time validation) blocks feature acceptance
- T067 (system validation time) blocks feature acceptance
- All wizard framework tasks (T032-T036) must implement timeout handling
- All context detection tasks (T028-T031) must meet 500ms response requirement

## Parallel Execution Examples

### Phase 3.2 - Contract Tests (All Parallel)
```bash
# Launch T005-T009 (model tests) together:
Task: "Contract test CommandContext model validation in tests/contract/test_command_context_model.py"
Task: "Contract test WizardState model validation in tests/contract/test_wizard_state_model.py"
Task: "Contract test ConfigurationState model validation in tests/contract/test_configuration_state_model.py"
Task: "Contract test FlagDefinition model validation in tests/contract/test_flag_definition_model.py"
Task: "Contract test WizardStep model validation in tests/contract/test_wizard_step_model.py"

# Launch T010-T013 (CLI tests) together:
Task: "Contract test enhanced shelf command behavior in tests/contract/test_shelf_command_enhanced.py"
Task: "Contract test enhanced box command behavior in tests/contract/test_box_command_enhanced.py"
Task: "Contract test enhanced fill command routing in tests/contract/test_fill_command_enhanced.py"
Task: "Contract test enhanced serve command with wizards in tests/contract/test_serve_command_enhanced.py"
```

### Phase 3.3 - Core Models (All Parallel)
```bash
# Launch T023-T027 (data models) together:
Task: "CommandContext model in src/models/command_context.py"
Task: "WizardState model in src/models/wizard_state.py"
Task: "ConfigurationState model in src/models/configuration_state.py"
Task: "FlagDefinition model in src/models/flag_definition.py"
Task: "WizardStep model in src/models/wizard_step.py"
```

### Phase 3.5 - Performance Tests (All Parallel)
```bash
# Launch T056-T058 (performance validation) together:
Task: "Performance tests for context detection (<500ms) in tests/performance/test_context_performance.py"
Task: "Performance tests for wizard step transitions (<200ms) in tests/performance/test_wizard_performance.py"
Task: "Memory usage tests for wizard sessions (<50MB) in tests/performance/test_memory_usage.py"
```

## Task Specifications

### Critical Success Criteria
- **Context Detection**: Commands must detect missing entities and offer creation within 500ms
- **Wizard Flow**: Setup wizards must complete all steps with <200ms transitions
- **Flag Consistency**: All commands must support standardized flags with single-letter short forms
- **Memory Efficiency**: Wizard sessions must use <50MB memory per active session
- **Database Compatibility**: All features must work identically with SQLite-vec and Qdrant
- **Constitutional Performance**: Complete setup <30s, system validation <5s (T065, T066)

### Validation Checklist
*GATE: Must pass before marking feature complete*

- [ ] All contracts have corresponding tests (T005-T018 ✓)
- [ ] All entities have model tasks (T023-T027 ✓)
- [ ] All tests come before implementation (Phase 3.2 before 3.3 ✓)
- [ ] Parallel tasks truly independent (file-level separation ✓)
- [ ] Each task specifies exact file path (all tasks ✓)
- [ ] No task modifies same file as another [P] task (verified ✓)

## Notes
- **[P] tasks** = different files, no dependencies - can run simultaneously
- **Critical TDD Rule**: Verify ALL tests fail before implementing any functionality
- **Commit Strategy**: Commit after each completed task to maintain atomic changes
- **Error Handling**: Each component must handle failures gracefully with user-friendly messages
- **Performance Monitoring**: Include timing and memory metrics in all services

## Task Count Summary
- **Setup**: 4 tasks
- **Contract Tests**: 18 tasks (14 [P])
- **Core Implementation**: 21 tasks (9 [P])
- **Integration**: 10 tasks (4 [P])
- **Polish**: 14 tasks (12 [P])
- **Total**: 67 tasks (39 parallel, 28 sequential)

**Estimated Timeline**:
- Phase 3.1 (Setup): 1-2 days
- Phase 3.2 (Tests): 3-4 days (many parallel)
- Phase 3.3 (Core): 5-7 days
- Phase 3.4 (Integration): 2-3 days
- Phase 3.5 (Polish): 2-3 days
- **Total**: 13-19 days