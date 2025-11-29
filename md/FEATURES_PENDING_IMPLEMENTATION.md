# Features Pending Implementation

**Status**: 980 failing tests across 8 major feature categories
**Date**: 2025-09-29
**Context**: Test-Driven Development (TDD) - tests exist first, implementation needed

---

## Executive Summary

Bablib has undergone a major architectural evolution from a simple documentation crawler to a sophisticated Shelf-Box Rhyme System with context-aware commands. The tests for these features have been written following TDD principles, but the actual implementations are incomplete or missing. This document provides a comprehensive overview of what needs to be built.

---

## Category 1: Context-Aware CLI Commands (HIGH PRIORITY)

### Overview
The vision is to create a CLI that "understands" the user's intent and current state. When a user references a shelf or box that doesn't exist, the system should detect this and offer to create it. When they access an empty box, it should suggest filling it with appropriate content based on the box type.

### 1.1 Shelf Command Enhancements

**Status**: Partially implemented (basic CRUD exists, context awareness missing)
**Tests**: 17 failing tests in `tests/contract/shelf/test_cli_shelf_commands.py`
**Priority**: HIGH - Foundation for entire Shelf-Box system

#### What Needs to Be Built

**Context Detection & Creation Prompts**
When a user runs `bablib shelf my-docs` and the shelf doesn't exist:
- Detect the missing shelf via ContextService
- Prompt: "Shelf 'my-docs' not found. Create it? (y/n)"
- If yes → create shelf
- Follow-up prompt: "Launch setup wizard? (y/n)"
- If yes → run ShelfWizard for configuration

**Interactive Shelf Wizard**
A step-by-step guided setup when creating a new shelf:
```
Step 1/4: Description
  Enter a description for 'my-docs': _

Step 2/4: Auto-fill Configuration
  Automatically fill this shelf when created? (y/n): _

Step 3/4: Default Box Type
  Choose default box type for new boxes:
  → 1. drag (websites)
    2. rag (documents)
    3. bag (files)

Step 4/4: Tags
  Enter tags (comma-separated): python, api, docs

✓ Shelf 'my-docs' configured successfully!
```

**Enhanced Shelf Listing**
- Verbose mode shows: box count, total content items, last modified
- Filter by current shelf only
- Show status indicators: [empty], [configured], [active]
- Color-coded output using Rich library

**Shelf State Management**
- Track "current shelf" concept (like git branches)
- Commands default to current shelf unless specified
- Visual indicator in CLI prompt when shelf is set
- Easy switching: `bablib shelf current my-other-docs`

**Implementation Location**: `src/cli/commands/shelf.py`

**Key Integration Points**:
- `ContextService` - Detect shelf existence and status
- `WizardOrchestrator` - Launch and manage wizard flow
- `ShelfWizard` - Collect configuration data
- `ShelfService` - Perform CRUD operations
- Universal arrow navigation for wizard steps

---

### 1.2 Box Command Enhancements

**Status**: Partially implemented (basic create exists, type-aware features missing)
**Tests**: 13 failing tests in `tests/contract/test_box_create.py`
**Priority**: HIGH - Core content organization

#### What Needs to Be Built

**Type-Aware Box Creation**
Three box types with different behaviors:
- **drag boxes**: For crawling websites (URL validation, crawl depth, rate limits)
- **rag boxes**: For document ingestion (file paths, chunk size, overlap)
- **bag boxes**: For simple file storage (directory patterns, recursion)

**Box Inspection with Smart Prompts**
When user accesses an empty box, provide type-specific guidance:

```bash
$ bablib box web-docs
Box 'web-docs' (drag) is empty.

Options:
1. Fill with website URL
2. Configure auto-crawl schedule
3. View box settings

Choose option (1-3): 1
Enter website URL to crawl: https://docs.python.org
Crawling depth (1-10) [3]: 5
Max pages [1000]: 2000

✓ Started crawl: 0/2000 pages (eta: 15m)
```

**Box Wizard Integration**
Interactive setup when creating boxes:
```
Creating box 'api-docs' (type: drag)

Step 1/5: Description
  What is this box for?: Python API documentation

Step 2/5: Initial Source
  Provide initial website to crawl? (y/n): y
  URL: https://api.myproject.com/docs

Step 3/5: Crawl Settings
  Maximum depth (1-10) [3]: 4
  Rate limit (req/sec) [1.0]: 2.0

Step 4/5: Auto-Process
  Automatically start crawling now? (y/n): y

Step 5/5: Shelf Assignment
  Add to shelf: my-docs

✓ Box 'api-docs' created and crawling started!
```

**Global Box Uniqueness**
- Box names must be globally unique (not just per-shelf)
- Clear error messages when duplicate detected
- Suggest alternatives: "Box 'api-docs' exists. Try: api-docs-v2, api-docs-new"

**Box Relationships**
- Add box to multiple shelves
- Remove box from shelf (doesn't delete box)
- List all boxes across all shelves
- Filter boxes by type, shelf, or status

**Implementation Location**: `src/cli/commands/box.py`

**Key Integration Points**:
- `BoxService` - CRUD operations
- `BoxWizard` - Interactive setup
- `ContextService` - Detect box status
- Type validation using `BoxType` enum
- Shelf relationship management

---

### 1.3 Fill Command Type-Based Routing

**Status**: Not implemented (placeholder exists)
**Tests**: 14 failing tests in `tests/contract/test_fill_command.py`
**Priority**: HIGH - Core functionality for content management

#### What Needs to Be Built

**Intelligent Type Detection & Routing**
The fill command should automatically route to the correct subsystem based on box type:

```bash
# For drag boxes → route to crawler
$ bablib fill web-docs --source https://docs.example.com
Detected: drag box 'web-docs'
Routing to: Website Crawler
Crawling https://docs.example.com...
  ├─ Found 150 pages
  ├─ Processing depth 1/3
  └─ ETA: 8 minutes

# For rag boxes → route to document uploader
$ bablib fill doc-collection --source ./technical-docs/
Detected: rag box 'doc-collection'
Routing to: Document Uploader
Scanning ./technical-docs/...
  ├─ Found 45 PDF files
  ├─ Chunking with 500 token size
  └─ Embedding with mxbai-embed-large

# For bag boxes → route to file storage
$ bablib fill assets --source ./images/ --pattern "*.png"
Detected: bag box 'assets'
Routing to: File Storage
Storing files from ./images/...
  ├─ Found 230 PNG files (45.2 MB)
  ├─ Copying to storage
  └─ Complete in 3 seconds
```

**Type-Specific Flag Validation**
Only show and accept flags appropriate for the box type:

**Drag boxes (websites)**:
- `--max-pages <int>` - Maximum pages to crawl
- `--depth <int>` - Crawl depth (default: 3)
- `--rate-limit <float>` - Requests per second
- `--follow-external` - Follow external links

**Rag boxes (documents)**:
- `--chunk-size <int>` - Token size per chunk
- `--overlap <int>` - Chunk overlap tokens
- `--recursive` - Process subdirectories
- `--extensions <list>` - File types (.pdf, .md, .txt)

**Bag boxes (storage)**:
- `--pattern <glob>` - File pattern (*.jpg, *.pdf)
- `--recursive` - Include subdirectories
- `--preserve-structure` - Keep directory layout
- `--metadata` - Extract and store file metadata

**Source Validation by Type**
- Drag: Must be valid HTTP(S) URL, check accessibility
- Rag: Must be valid file path or directory, check permissions
- Bag: Must be valid directory, check existence

**Progress Reporting**
Type-specific progress indicators:
- Drag: Pages crawled, links found, errors encountered
- Rag: Files processed, chunks created, embeddings generated
- Bag: Files copied, size transferred, duplicate handling

**Error Handling with Suggestions**
```bash
$ bablib fill web-docs --source /path/to/local/files
Error: Box 'web-docs' is type 'drag' (websites only)

  You provided: Local file path
  Expected: HTTP/HTTPS URL

Suggestions:
  1. Use a different box:
     bablib fill local-files --source /path/to/local/files

  2. Create a rag box for this content:
     bablib box create local-files --type rag
     bablib fill local-files --source /path/to/local/files
```

**Implementation Location**: `src/cli/commands/fill.py`

**Key Integration Points**:
- `BoxService` - Get box type and configuration
- `DocumentationCrawler` - Handle drag boxes
- Document uploader service - Handle rag boxes
- File storage service - Handle bag boxes
- `ContextService` - Verify box exists
- Type-specific validators in `src/lib/validators/`

---

## Category 2: MCP Server Shelf Integration (HIGH PRIORITY)

### Overview
The MCP (Model Context Protocol) server needs to be extended to support the new Shelf-Box architecture. AI assistants like Claude should be able to query shelf structure, list boxes by shelf, and perform admin operations through dedicated endpoints.

### 2.1 MCP Context Endpoints

**Status**: Not implemented
**Tests**: 21 failing tests in `tests/contract/shelf/test_mcp_shelf_endpoints.py`
**Priority**: HIGH - Critical for AI assistant integration

#### What Needs to Be Built

**GET /context/shelf/{name}**
Retrieve complete context about a shelf including its status and contents:

```json
Request:
GET http://localhost:9383/context/shelf/my-docs

Response (200 OK):
{
  "name": "my-docs",
  "exists": true,
  "configuration_state": {
    "is_configured": true,
    "has_content": true,
    "needs_migration": false
  },
  "box_count": 5,
  "empty_box_count": 1,
  "boxes": [
    {
      "name": "web-docs",
      "type": "drag",
      "is_empty": false,
      "item_count": 150,
      "last_updated": "2025-09-29T10:30:00Z"
    },
    {
      "name": "api-docs",
      "type": "rag",
      "is_empty": true,
      "item_count": 0,
      "last_updated": null
    }
  ],
  "last_modified": "2025-09-29T10:30:00Z",
  "suggested_actions": [
    "Fill empty box 'api-docs'",
    "Run search across all boxes",
    "Export shelf contents"
  ]
}

Response (404 Not Found):
{
  "error": "shelf_not_found",
  "message": "Shelf 'my-docs' does not exist",
  "suggestions": [
    "Create shelf: POST /admin/shelf/create",
    "List existing shelves: GET /shelf/list"
  ]
}
```

**GET /context/box/{name}**
Retrieve complete context about a specific box:

```json
Request:
GET http://localhost:9383/context/box/web-docs

Response (200 OK):
{
  "name": "web-docs",
  "type": "drag",
  "exists": true,
  "configuration_state": {
    "is_configured": true,
    "has_content": true,
    "needs_migration": false
  },
  "shelves": ["my-docs", "production-docs"],
  "is_empty": false,
  "item_count": 150,
  "size_bytes": 5242880,
  "last_updated": "2025-09-29T10:30:00Z",
  "type_specific_config": {
    "source_url": "https://docs.example.com",
    "max_depth": 3,
    "last_crawl": "2025-09-29T08:00:00Z",
    "crawl_status": "completed"
  },
  "suggested_actions": [
    "Update content: POST /admin/box/fill",
    "Search within box: POST /search?box=web-docs",
    "Export box: POST /admin/box/export"
  ]
}
```

**GET /shelf/list**
List all shelves with basic info:

```json
Request:
GET http://localhost:9383/shelf/list?include_empty=false

Response (200 OK):
{
  "shelves": [
    {
      "name": "my-docs",
      "box_count": 5,
      "total_items": 450,
      "is_current": true,
      "last_modified": "2025-09-29T10:30:00Z"
    },
    {
      "name": "archive",
      "box_count": 12,
      "total_items": 2300,
      "is_current": false,
      "last_modified": "2025-09-20T15:00:00Z"
    }
  ],
  "total_shelves": 2,
  "current_shelf": "my-docs"
}
```

**Enhanced /projects/list with Shelf Filter**
Add shelf filtering to existing project list endpoint:

```json
Request:
GET http://localhost:9383/projects/list?shelf=my-docs

Response (200 OK):
{
  "projects": [
    {
      "name": "web-docs",
      "type": "drag",
      "shelf": "my-docs",
      "items": 150,
      "last_updated": "2025-09-29T10:30:00Z"
    }
  ],
  "total": 1,
  "filter_applied": {
    "shelf": "my-docs"
  }
}
```

**Enhanced /projects/search with Shelf Awareness**
Make search shelf-aware:

```json
Request:
POST http://localhost:9383/projects/search
{
  "query": "authentication API",
  "shelf": "my-docs",
  "limit": 10
}

Response (200 OK):
{
  "results": [
    {
      "content": "API authentication uses JWT tokens...",
      "box": "api-docs",
      "shelf": "my-docs",
      "relevance": 0.89,
      "url": "https://api.example.com/auth"
    }
  ],
  "total_results": 15,
  "search_context": {
    "shelf": "my-docs",
    "boxes_searched": ["api-docs", "web-docs"],
    "query_time_ms": 45
  }
}
```

**Implementation Location**:
- `src/logic/mcp/core/read_only_server.py` - Endpoint registration
- `src/logic/mcp/services/read_only_service.py` - Business logic
- `src/logic/mcp/models/shelf_context.py` - Response models

---

### 2.2 MCP Admin Shelf Operations

**Status**: Not implemented
**Tests**: Tests in `tests/contract/test_mcp_admin_shelf.py` and `test_mcp_admin_box.py`
**Priority**: MEDIUM - Admin functionality for AI assistants

#### What Needs to Be Built

**POST /admin/shelf/create**
Create new shelf via MCP admin server (localhost only):

```json
Request:
POST http://127.0.0.1:9384/admin/shelf/create
{
  "name": "production-docs",
  "description": "Production documentation",
  "set_current": true,
  "auto_fill": false
}

Response (201 Created):
{
  "success": true,
  "shelf": {
    "name": "production-docs",
    "created_at": "2025-09-29T10:35:00Z",
    "is_current": true
  },
  "message": "Shelf 'production-docs' created successfully"
}
```

**POST /admin/box/create**
Create new box via MCP:

```json
Request:
POST http://127.0.0.1:9384/admin/box/create
{
  "name": "prod-api-docs",
  "type": "drag",
  "shelf": "production-docs",
  "description": "Production API documentation",
  "config": {
    "source_url": "https://api.prod.example.com/docs",
    "max_depth": 3,
    "auto_start": true
  }
}

Response (201 Created):
{
  "success": true,
  "box": {
    "name": "prod-api-docs",
    "type": "drag",
    "shelf": "production-docs",
    "created_at": "2025-09-29T10:40:00Z"
  },
  "crawl_started": true,
  "message": "Box created and crawl initiated"
}
```

**POST /admin/shelf/add-box**
Add existing box to a shelf:

```json
Request:
POST http://127.0.0.1:9384/admin/shelf/add-box
{
  "shelf": "production-docs",
  "box": "existing-box"
}

Response (200 OK):
{
  "success": true,
  "message": "Box 'existing-box' added to shelf 'production-docs'"
}
```

**POST /admin/wizards/start**
Start an interactive wizard session:

```json
Request:
POST http://127.0.0.1:9384/admin/wizards/start
{
  "wizard_type": "shelf",
  "entity_name": "my-new-docs"
}

Response (200 OK):
{
  "session_id": "wiz_550e8400",
  "wizard_type": "shelf",
  "current_step": 1,
  "total_steps": 4,
  "step_prompt": "Enter a description for 'my-new-docs':",
  "step_type": "text_input",
  "validation_rules": {
    "max_length": 200,
    "required": false
  }
}
```

**POST /admin/wizards/{session_id}/step**
Submit wizard step response:

```json
Request:
POST http://127.0.0.1:9384/admin/wizards/wiz_550e8400/step
{
  "response": "Main documentation collection for the project"
}

Response (200 OK):
{
  "session_id": "wiz_550e8400",
  "current_step": 2,
  "total_steps": 4,
  "step_prompt": "Automatically fill this shelf when created?",
  "step_type": "boolean",
  "progress": 0.25
}
```

**Implementation Location**:
- `src/logic/mcp/core/admin_server.py` - Endpoint registration
- `src/logic/mcp/services/admin_service.py` - Business logic
- `src/logic/mcp/models/admin_operations.py` - Request/response models
- Security: Localhost-only binding enforcement

---

## Category 3: Wizard Framework (MEDIUM PRIORITY)

### Overview
A comprehensive wizard system for guiding users through complex setup processes. Wizards provide step-by-step configuration with validation, suggestions, and progress tracking.

**Status**: Partially implemented (basic structure exists, specific wizards missing)
**Tests**: Tests in `tests/unit/test_wizard_transitions.py`, `tests/performance/test_wizard_performance.py`
**Priority**: MEDIUM - Enhances user experience significantly

### What Needs to Be Built

**ShelfWizard - Shelf Configuration**
Guides user through shelf setup:
- Step 1: Description (optional text)
- Step 2: Auto-fill setting (boolean)
- Step 3: Default box type (choice: drag/rag/bag)
- Step 4: Tags (comma-separated list)

**BoxWizard - Type-Aware Box Setup**
Adapts questions based on box type:

For drag boxes:
- Initial URL to crawl
- Maximum depth (1-10)
- Rate limit (requests/second)
- Follow external links (y/n)

For rag boxes:
- Initial document directory
- File extensions to process
- Chunk size (tokens)
- Chunk overlap (tokens)

For bag boxes:
- Initial directory
- File patterns (globs)
- Preserve directory structure (y/n)
- Extract metadata (y/n)

**McpWizard - MCP Server Configuration**
Setup MCP servers through wizard:
- Enable read-only server (y/n)
- Read-only port [9383]
- Enable admin server (y/n)
- Admin port [9384]
- Auto-start with system (y/n)

**Wizard Features**:
- Progress indicator (Step 2/4)
- Back button support (←)
- Input validation with immediate feedback
- Suggestions based on context
- Ability to skip optional steps
- Summary review before completion
- State persistence (can resume later)

**Performance Requirements**:
- Step transition: <200ms
- Validation: <100ms
- Complete wizard: <5 minutes user time
- Memory: <50MB per session

**Implementation Location**:
- `src/logic/wizard/shelf_wizard.py`
- `src/logic/wizard/box_wizard.py`
- `src/logic/wizard/mcp_wizard.py`
- `src/logic/wizard/orchestrator.py` - Session management
- `src/logic/wizard/validator.py` - Input validation

---

## Category 4: Integration & Performance (MEDIUM PRIORITY)

### 4.1 Integration Test Scenarios

**Status**: Failing due to incomplete implementations
**Tests**: 40+ tests in `tests/integration/`
**Priority**: MEDIUM - Validates end-to-end workflows

#### Key Scenarios to Fix

**New User Setup Workflow**
Complete journey from nothing to working system:
1. Run `bablib setup`
2. Choose vector store (SQLite-vec or Qdrant)
3. System validation passes
4. Create first shelf via wizard
5. Create first box in shelf
6. Fill box with initial content
7. Verify content searchable

**Content Filling by Type**
Test each box type's fill workflow:
1. Create drag box
2. Fill with website URL
3. Verify pages crawled and indexed
4. Create rag box
5. Fill with PDF documents
6. Verify chunks and embeddings created
7. Create bag box
8. Fill with image files
9. Verify files stored with metadata

**MCP Server Setup & Usage**
Complete MCP integration:
1. Start both servers (read-only + admin)
2. Verify Claude can connect
3. Create shelf via MCP admin
4. Create box via MCP admin
5. Fill box via MCP admin
6. Search content via MCP read-only
7. Retrieve files via MCP read-only

**Implementation Locations**: Multiple services, primarily testing existing features work together

---

### 4.2 Performance Requirements

**Status**: Tests exist but features not optimized
**Tests**: 15+ tests in `tests/performance/`
**Priority**: MEDIUM - Critical for user experience

#### Performance Targets

**Context Detection**:
- Shelf existence check: <500ms
- Box existence check: <300ms
- With cache hit: <50ms
- Cache TTL: 5 minutes

**Wizard Operations**:
- Launch wizard: <200ms
- Step transition: <200ms
- Input validation: <100ms
- Complete session: User time <5min, system time <1sec

**MCP Endpoints**:
- Context queries: <500ms
- List operations: <1sec (1000 items)
- Search queries: <2sec (10k documents)
- Admin operations: <3sec

**CLI Commands**:
- Help display: <100ms
- Shelf list: <500ms
- Box list: <500ms
- Fill command start: <1sec (initiation only)

**Implementation**: Performance testing and optimization across all services

---

## Category 5: Legacy Test Cleanup (LOW PRIORITY)

### Overview
Several test files reference old architecture and need to be deleted or completely rewritten.

**Status**: Tests fail because they reference deleted code
**Tests**: ~150 tests across multiple files
**Priority**: LOW - Delete rather than fix

### Files to Delete

1. **test_cli_batch_crawl.py** - Uses removed BatchCrawler class
2. **test_cli_crawl_update.py** - Uses removed ProjectManager class
3. **test_cli_create_wizard.py** - Old wizard structure
4. **test_setup_wizard_contract.py** - Replaced by new wizard framework
5. **test_project_create_cli.py** - Uses old project concept
6. **test_project_list_cli.py** - Uses old project concept
7. **test_project_remove_cli.py** - Uses old project concept
8. **test_upload_files_cli.py** - Uses removed UploadManager class

### Files to Review & Update

1. **test_cli_commands_existing.py** - Some tests may be salvageable
2. **test_command_aliases.py** - Verify aliases still valid
3. **test_file_validation.py** - Update for new box/fill validation
4. **test_upload_sources.py** - Rewrite for fill command
5. **test_box_model.py** - Update for current Box model

**Action**: Delete legacy files, update salvageable ones

---

## Implementation Priority Matrix

### Phase 1 (Weeks 1-2): Core Functionality
**Goal**: Basic Shelf-Box commands working

1. Context-aware shelf commands (Category 1.1)
2. Context-aware box commands (Category 1.2)
3. Fill command routing (Category 1.3)

**Impact**: Enables basic usage of new architecture
**Tests Fixed**: ~200 tests
**User Value**: Users can create and use shelves/boxes

---

### Phase 2 (Weeks 3-4): MCP Integration
**Goal**: AI assistants can interact with Bablib

1. MCP context endpoints (Category 2.1)
2. MCP admin operations (Category 2.2)
3. Enhanced search with shelf awareness

**Impact**: Full AI assistant integration
**Tests Fixed**: ~150 tests
**User Value**: Claude can manage documentation

---

### Phase 3 (Weeks 5-6): User Experience
**Goal**: Smooth guided setup and usage

1. Wizard framework completion (Category 3)
2. Interactive prompts and suggestions
3. Progress reporting and status display

**Impact**: Significantly improved UX
**Tests Fixed**: ~100 tests
**User Value**: Easier onboarding and usage

---

### Phase 4 (Weeks 7-8): Polish & Performance
**Goal**: Production-ready system

1. Integration test fixes (Category 4.1)
2. Performance optimization (Category 4.2)
3. Legacy test cleanup (Category 5)
4. Documentation updates

**Impact**: Production stability
**Tests Fixed**: ~200 tests
**User Value**: Fast, reliable system

---

## Success Criteria

### Quantitative Metrics
- **Test Pass Rate**: >95% (2100+ of 2237 tests passing)
- **Performance**: All targets met per Category 4.2
- **Code Coverage**: >85% for new features
- **API Response Time**: <1sec for 95th percentile

### Qualitative Goals
- **User Onboarding**: New user to first successful search <5 minutes
- **CLI Intuitiveness**: Users discover features through help and prompts
- **AI Integration**: Claude can perform all operations without errors
- **Error Messages**: Clear, actionable error messages with suggestions

---

## Technical Debt Notes

### Current Issues
1. **Mixed Architecture**: Some parts still use old project concept
2. **Incomplete Validation**: Box/shelf name validation not comprehensive
3. **Error Handling**: Inconsistent error messages and codes
4. **Documentation**: CLAUDE.md needs update after implementation
5. **Deprecation Warnings**: ~500 warnings need fixing

### Future Considerations
1. **Multi-User Support**: Current design is single-user
2. **Remote Storage**: Only local storage currently supported
3. **Concurrent Operations**: Limited support for parallel box filling
4. **Backup/Restore**: Shelf-level backup not implemented
5. **Migration Tools**: No tools to migrate old projects to shelves

---

## Appendix: Test File Reference

### High-Value Test Files (Implement First)
```
tests/contract/shelf/test_cli_shelf_commands.py      # 17 tests - Shelf CLI
tests/contract/test_box_create.py                    # 13 tests - Box creation
tests/contract/test_fill_command.py                  # 14 tests - Fill routing
tests/contract/shelf/test_mcp_shelf_endpoints.py     # 21 tests - MCP integration
tests/contract/test_mcp_context_shelf.py             # Context endpoints
tests/contract/test_mcp_context_box.py               # Context endpoints
tests/integration/test_new_user_setup.py             # E2E workflow
tests/integration/test_content_filling_by_type.py    # Type-based fill
```

### Medium-Value Test Files (Implement Second)
```
tests/contract/test_mcp_admin_shelf.py               # Admin operations
tests/contract/test_mcp_admin_box.py                 # Admin operations
tests/contract/test_mcp_wizard_start.py              # Wizard via MCP
tests/unit/test_wizard_transitions.py                # Wizard state
tests/unit/test_context_detection.py                 # Context service
tests/performance/test_wizard_performance.py         # Wizard speed
tests/performance/test_context_performance.py        # Context speed
```

### Low-Priority (Delete or Update Later)
```
tests/contract/test_cli_batch_crawl.py               # DELETE
tests/contract/test_cli_crawl_update.py              # DELETE
tests/contract/test_project_*_cli.py                 # DELETE (3 files)
tests/contract/test_upload_files_cli.py              # DELETE
tests/manual/*                                        # REVIEW/DELETE
```

---

**End of Document**

*For implementation details and task breakdown, see TASKS_TEST_FIXES.md*
*For current architecture, see CLAUDE.md*