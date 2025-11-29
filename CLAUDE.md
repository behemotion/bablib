# Bablib Development Guidelines

**Last Updated:** 2025-09-30

**IMPORTANT:** This file must be updated every time new functional changes are implemented. Keep the content under 40,000 characters by removing outdated details when adding new content.

## Project Overview
Bablib is a documentation crawler and search tool with RAG capabilities and MCP server integration. Features single-command UV installation with unified setup operations and the new Shelf-Box Rhyme System for intuitive documentation organization.

### Documentation File Rules:
1. **Documentation files (*.md)** → `./md/` (ONLY create .md files in this directory unless explicitly specified otherwise)
2. **ALL .md files MUST be created in `./md/` directory** (unless user explicitly specifies a different location or file path is defined in CLAUDE.md)
3. When user asks to access/read a .md file without a full path:
   - First look in `./md/` directory
   - Only search elsewhere if not found in `./md/`
4. Exception: Root-level files like README.md, CLAUDE.md, constitution.md stay in their designated locations

## Implementation Status
✅ **100% Complete** - Installation Process Reorganization + Unified Setup Command + Full Vector Store Support + Shelf-Box Rhyme System + Context-Aware Commands

### Core Components
- **UV Installation** - Single command: `uv tool install git+https://github.com/behemotion/bablib`
- **Shelf-Box Rhyme System** - Intuitive document organization: Shelves (collections) contain Boxes (drag/rag/bag types)
- **Context-Aware Commands** - Automatic entity detection with creation prompts and setup wizards (NEW)
- **Interactive Wizards** - Step-by-step setup for shelves, boxes, and MCP servers via `--init` flag (NEW)
- **Unified Fill Command** - Type-based routing: drag→crawler, rag→uploader, bag→storage
- **Unified Setup System** - All operations under `bablib setup` with flag-based routing
- **Universal Arrow Navigation** - Consistent keyboard navigation across all CLI interfaces
- **Interactive Menu** - Rich-based UI for guided setup when no flags provided
- **Vector Store Selection** - Runtime choice between SQLite-vec and Qdrant with factory pattern
- **Setup Orchestration** - Centralized coordinator for all installation operations
- **Service Detection** - Async detection of Docker, Qdrant, Ollama, Python, UV, Git
- **Documentation Crawler** - Reorganized under `src/logic/crawler/` with functional grouping
- **MCP Server** - FastAPI with context-aware endpoints and wizard integration (ENHANCED)
- **Setup Logic** - Reorganized under `src/logic/setup/` with service-oriented architecture

## Tech Stack
- **Python 3.13+**, **UV/UVX 0.8+** - Package management
- **SQLite-vec** - Local vector database (no external dependencies)
- **Qdrant 1.15.1** - Scalable vector database (optional)
- **Ollama** - Embeddings (mxbai-embed-large)
- **FastAPI** - MCP server with REST API
- **Click + Rich** - CLI with progress UI
- **Pydantic v2** - Data validation with enum support
- **pytest + pytest-asyncio** - Testing

## Project Structure
```
src/
├── models/              # Pydantic models (settings, configurations)
├── services/            # Core services (database, vector store, embeddings)
├── cli/                 # CLI commands (setup, create, crawl, serve)
│   └── utils/           # Universal CLI utilities (navigation, etc.)
├── lib/                 # Utilities and logging
└── logic/               # Reorganized business logic
    ├── setup/           # Setup operations
    │   ├── core/        # SetupOrchestrator, CommandRouter, InteractiveMenu
    │   ├── services/    # SetupInitializer, Uninstaller, Configurator, etc.
    │   ├── models/      # SetupOperation, Configuration, MenuState, etc.
    │   └── utils/       # ProgressReporter, user prompts
    ├── crawler/         # Crawler logic
    │   ├── core/        # DocumentationCrawler, BatchCrawler
    │   ├── analytics/   # ErrorReporter, CrawlReport
    │   ├── utils/       # ProgressReporter, CrawlProgressDisplay
    │   └── models/      # CrawlSession, Page, BatchOperation, ErrorEntry
    └── mcp/             # MCP server logic (NEW)
        ├── core/        # McpReadOnlyServer, McpAdminServer, ServerOrchestrator
        ├── services/    # ReadOnlyMcpService, AdminMcpService, CommandExecutor
        ├── models/      # McpServerConfig, McpResponse, FileAccessRequest
        └── utils/       # PortManager, ConfigGenerator, Security
tests/
├── contract/            # API contract tests (setup, crawl, MCP)
├── integration/         # End-to-end tests (setup flows, legacy commands)
├── unit/               # Model/service tests (flag validation, routing)
└── performance/        # <30s validation tests (setup, menu responsiveness)
```

### Default Shelf Behavior

On first installation/migration, Bablib automatically creates a default shelf named **"common shelf"** with:
- `is_default = TRUE` - Marked as the default shelf
- `is_deletable = FALSE` - Cannot be deleted (protection rule)
- Contains one default box: "new year" (rag type)
- Location: src/services/database_migrator.py:125-130 (_create_default_shelf_data method)

This ensures users always have at least one shelf available for immediate use.

## Installation

```bash
# Single command installation with automatic setup
uv tool install git+https://github.com/behemotion/bablib

# Commands available after installation
bablib setup              # Unified setup command (interactive or flag-based)
bablib shelf              # Manage documentation shelves (collections)
bablib box                # Manage documentation boxes (drag/rag/bag)
bablib fill               # Fill boxes with content (unified routing)
bablib serve              # MCP server for AI assistants
bablib health             # System health checks
```

**Key Features:**
- ✅ <30s installation with automatic setup
- ✅ Unified setup command for all operations
- ✅ Interactive menu with Rich UI when no flags provided
- ✅ Vector database selection (SQLite-vec or Qdrant) with runtime switching
- ✅ System validation (Python 3.13+, 4GB RAM, 2GB disk)
- ✅ Async service detection (Docker, Qdrant, Ollama, SQLite-vec, UV, Git)
- ✅ Graceful fallback when services unavailable

## Commands

### Core Commands
```bash
# Shelf Management (Collections)
bablib shelf create <name> [--shelf-description "text"] [--set-current]
bablib shelf list [--verbose] [--current-only] [--limit 10]
bablib shelf current [<name>]                   # Get or set current shelf
bablib shelf rename <old_name> <new_name>       # Rename shelf
bablib shelf delete <name> [--force] [--no-backup]

# NOTE: Creating a shelf automatically creates a default RAG box named "<shelf_name>_box"
#       This behavior is by design to ensure every shelf has at least one box for content storage
#       Location: src/services/shelf_service.py:62-67 (create_shelf method)

# Box Management (Documentation Units)
bablib box create <name> --type <drag|rag|bag> [--shelf <name>] [--box-description "text"]
bablib box list [--shelf <name>] [--type <type>] [--verbose] [--limit 10]
bablib box add <box_name> --to-shelf <shelf_name>    # Add box to shelf
bablib box remove <box_name> --from-shelf <shelf_name>    # Remove box from shelf
bablib box rename <old_name> <new_name>         # Rename box
bablib box delete <name> [--force]              # Delete box

# Unified Fill Command (Type-Based Routing)
bablib fill <box_name> --source <url_or_path> [--shelf <name>]
# Drag boxes (websites): --max-pages, --rate-limit, --depth
# Rag boxes (documents): --chunk-size, --overlap
# Bag boxes (files): --recursive, --pattern

# Documentation Management
# All documentation management is now handled through the unified Shelf-Box Rhyme System

# Unified Setup & Configuration
bablib setup                           # Interactive menu
bablib setup --init --auto             # Quick initialization
bablib setup --init --vector-store sqlite_vec
bablib setup --uninstall --force       # Force uninstall
bablib setup --reset --preserve-data   # Reset keeping projects

# Server Operations
bablib serve [--host 0.0.0.0] [--port 9382] [--foreground]    # Read-only MCP server (default)
bablib serve --admin [--host 127.0.0.1] [--port 9384]         # Admin MCP server (localhost only)
bablib health [--system] [--services] [--config] [--projects]
```

### Context-Aware Command Patterns (NEW)

**Feature**: Commands now detect missing entities and offer creation prompts with optional setup wizards.

#### Context Detection
All shelf and box commands now include context awareness:

```bash
# Accessing non-existent shelf prompts creation
bablib shelf my-docs
# > Shelf 'my-docs' not found. Create it? (y/n): y
# > Shelf created! Launch setup wizard? (y/n): y

# Accessing empty box prompts filling (type-aware)
bablib box web-docs
# > Box 'web-docs' is empty. Provide website URL to crawl? (y/n): y
# > Enter URL: https://docs.example.com
```

#### Setup Wizards
Use `--init` or `-i` flag to launch interactive setup wizards:

```bash
# Shelf wizard: description, auto-fill, default box type, tags
bablib shelf create docs --init

# Box wizard: type confirmation, description, auto-process, file patterns
bablib box create api-docs --type drag --init

# MCP server wizard: read-only/admin ports, auto-start configuration
bablib serve --init
```

#### Standardized Flags
All commands now support consistent short-form flags:

**Universal Flags**:
- `--init, -i`: Launch setup wizard
- `--verbose, -v`: Enable verbose output
- `--force, -F`: Force operation without prompts
- `--help, -h`: Show help information

**Type-Specific Flags**:
- `--type, -t`: Specify box type (drag|rag|bag)
- `--depth, -d`: Maximum crawl depth (drag boxes)
- `--recursive, -r`: Process directories recursively (rag/bag)
- `--rate-limit, -R`: Requests per second limit (drag boxes)

#### Context Service Architecture
Context detection powered by service layer:

**Services**:
- `ContextService`: Shelf/box existence checking with 5-minute cache
- `StatusDisplayService`: Entity status logic with suggestion generation
- `WizardOrchestrator`: Session management for interactive wizards

**Models**:
- `CommandContext`: Entity state (exists, is_empty, configuration_state)
- `WizardState`: Progress tracking (current_step, collected_data)
- `ConfigurationState`: Setup status (is_configured, has_content)

**Performance Requirements**:
- Context detection: <500ms
- Wizard step transitions: <200ms
- Memory usage: <50MB per wizard session

#### Wizard Integration Examples

```python
# Shelf wizard flow
from src.logic.wizard.shelf_wizard import ShelfWizard

wizard = ShelfWizard()
result = await wizard.run("my-shelf")
# Collects: description, auto_fill, default_box_type, tags

# Box wizard flow (type-aware)
from src.logic.wizard.box_wizard import BoxWizard

wizard = BoxWizard()
result = await wizard.run("my-box", "drag")
# Collects: description, auto_process, file_patterns, initial_source

# MCP wizard flow
from src.logic.wizard.mcp_wizard import McpWizard

wizard = McpWizard()
result = await wizard.run()
# Collects: enable_read_only, read_only_port, enable_admin, admin_port
```

#### MCP Context Endpoints
Enhanced MCP server with context-aware endpoints:

**Read-Only Server (Port 9383)**:
- `GET /context/shelf/{name}`: Get shelf context with box details
- `GET /context/box/{name}`: Get box context with suggested actions
- `GET /wizards/available`: List available setup wizards
- `GET /flags/definitions`: Get standardized flag mappings

**Admin Server (Port 9384)**:
- `POST /admin/context/create-shelf`: Create shelf with optional wizard
- `POST /admin/context/create-box`: Create box with type-aware config
- `POST /admin/wizards/start`: Start interactive wizard session
- `POST /admin/wizards/{id}/step`: Submit wizard step response

#### Error Handling Patterns
Context-aware error responses with actionable suggestions:

```python
# Missing entity detection
context = await context_service.check_shelf_exists("my-docs")
if not context.exists:
    if await prompt_create_shelf("my-docs"):
        await shelf_service.create("my-docs")
        if await prompt_setup_wizard():
            await wizard_orchestrator.run_shelf_wizard("my-docs")

# Empty entity prompting (type-aware)
context = await context_service.check_box_status("my-box")
if context.is_empty and context.box_type == "drag":
    url = await prompt_website_url()
    await fill_service.crawl_website("my-box", url)
```

### Testing
```bash
pytest tests/ -v                # All tests
pytest tests/performance/ -v    # Performance validation
pytest --cov=src tests/         # Coverage report
./.verify-package.sh             # Verify package installation integrity (CRITICAL after model changes)
```

## Configuration

### Directories (XDG-Compliant)
- `~/.config/bablib/` - Config files
- `~/.local/share/bablib/` - Data storage
- `~/.cache/bablib/` - Temp files

### Vector Store Configuration
- **SQLite-vec**: Local storage in `~/.local/share/bablib/projects/`
- **Qdrant**: External service at `http://localhost:6333`
- **Provider Selection**: Stored in `~/.config/bablib/settings.yaml`

### Environment Variables
```bash
# Vector Store
BABLIB_VECTOR_STORE=qdrant|sqlite_vec
BABLIB_QDRANT_URL=http://localhost:6333
BABLIB_SQLITE_VEC_PATH=/path/to/vectors.db

# Embeddings & Processing
BABLIB_OLLAMA_URL=http://localhost:11434
BABLIB_EMBEDDING_MODEL=mxbai-embed-large
BABLIB_CHUNK_SIZE=500
BABLIB_CHUNK_OVERLAP=50

# Crawling & Server
BABLIB_DEFAULT_CRAWL_DEPTH=3
BABLIB_DEFAULT_RATE_LIMIT=1.0
BABLIB_MCP_READ_ONLY_HOST=0.0.0.0
BABLIB_MCP_READ_ONLY_PORT=9383
BABLIB_MCP_ADMIN_HOST=127.0.0.1
BABLIB_MCP_ADMIN_PORT=9384
BABLIB_LOG_LEVEL=WARNING|INFO|DEBUG
```

## Vector Store Architecture

### Vector Store Selection
- **Interactive Mode**: User prompted to choose between SQLite-vec and Qdrant
- **Auto Mode**: Specify provider via `--vector-store` CLI option
- **Settings Persistence**: Choice saved in `GlobalSettings.vector_store_provider`
- **Runtime Factory**: `VectorStoreFactory` creates appropriate service instance

### Provider Models
- **VectorStoreProvider** - Enum with SQLITE_VEC and QDRANT options
- **SQLiteVecService** - Local vector storage with no external dependencies
- **VectorStoreService** - Qdrant-based scalable vector storage
- **VectorStoreFactory** - Runtime provider selection based on settings

### Setup Flow
1. System requirements validation (Python 3.13+, memory, disk)
2. Vector store provider selection (interactive) or CLI override
3. Provider-specific setup and validation
4. Settings persistence with enum serialization
5. Service availability warnings with setup instructions

### MCP Integration

#### Dual Server Architecture
- **Read-Only Server** (Port 9383): Provides safe read access to projects and documentation
  - Server name: `bablib` (renamed from bablib-mcp)
  - Project listing and search capabilities
  - File access with project-type-based restrictions
  - Vector search across project content
  - Health monitoring endpoints
- **Admin Server** (Port 9384): Full administrative control with security restrictions
  - Server name: `bablib-admin` (renamed from bablib-mcp-admin)
  - Complete Bablib command execution (with restrictions)
  - Project creation and management
  - Crawling operations and batch processing
  - Localhost-only binding for security
  - **BLOCKED OPERATIONS**: Uninstall, reset, and delete-all-projects operations are prohibited via MCP admin for security

#### Security Features
- **Network Isolation**: Admin server restricted to localhost (127.0.0.1) only
- **Access Control**: File access varies by project type (crawling=metadata, storage=full)
- **Input Sanitization**: Command injection and path traversal protection
- **Resource Limits**: Timeout enforcement and memory management
- **Operation Restrictions**: Critical system operations (uninstall, reset, delete-all) blocked via MCP admin

#### MCP Client Configuration
- **Auto-Generated Configs**: Client configuration files created in `mcp/` directory
- **Claude Code Integration**: Official CLI with dedicated MCP tools
- **Universal Compatibility**: Works with any MCP-compliant AI assistant
- **Concurrent Operations**: Both servers can run simultaneously on different ports

#### MCP Testing Requirements
**IMPORTANT**: MCP endpoints use the MCP protocol format, not standard REST/HTTP.

**Why Standard HTTP Testing Fails:**
- MCP is a specialized protocol for AI assistant integration
- Standard HTTP requests (curl, Postman, etc.) return: `{"detail": "Invalid method"}`
- MCP protocol includes request/response framing, session management, and capability negotiation

**Testing Requirements:**
- **Required Client**: MCP-compliant client (Claude Desktop, Claude Code, or custom MCP implementation)
- **Standard Tools**: curl/HTTP clients are insufficient for endpoint testing
- **Only Exception**: Health endpoint (`GET /mcp/v1/health`) supports standard REST/HTTP

**Development Testing Approaches:**
1. **Claude Desktop**: Official MCP client with built-in integration
2. **Claude Code**: Official CLI with dedicated MCP tools and file access
3. **MCP Protocol Client**: Implement using MCP specification (for advanced testing)
4. **Health Endpoint Only**: Use curl/HTTP for basic server status checks

**Endpoint Discovery:**
- Source code analysis (src/logic/mcp/core/)
- MCP protocol documentation at https://modelcontextprotocol.io
- Server logs during client connection

**Common Testing Mistakes:**
- ❌ Using curl to test search/execute endpoints → Always fails
- ❌ Expecting JSON-RPC format → MCP uses custom protocol
- ✅ Use health endpoint for HTTP connectivity tests only
- ✅ Use MCP client for full endpoint validation

## Universal Arrow Navigation Architecture

### Navigation Components
- **ArrowNavigator** (`src/cli/utils/navigation.py`) - Main navigation engine with cross-platform keyboard input
- **NavigationChoice** - Data structure for menu items with value, label, description, and styling
- **Universal Interface** - Consistent navigation behavior across all CLI components

### Navigation Features
- **Multi-Input Support**: ↑/↓ arrows, j/k vim keys, numbers 1-9, Enter, Escape/q, ? for help
- **Visual Highlighting**: Blue background for current selection with arrow indicator (`→`)
- **Cross-Platform**: Full keyboard support on Unix/macOS, graceful fallback on Windows/non-TTY
- **Accessibility**: Multiple navigation methods accommodate different user preferences

### Mandatory Navigation Requirements
1. **ArrowNavigator**: Full arrow key support (↑/↓) for sequential navigation
2. **AddressNavigator**: Direct number selection (1-9) for quick access
3. **Y/N Exclusion**: Never use numbered structure for yes/no confirmations - only y/n keys
4. **Option Descriptions**: Every selectable option MUST display a short descriptive label
5. **Status Display**: Show current status in short form for options where applicable (e.g., "[configured]", "[enabled]", "[running]")

### Implementation Patterns
- **Centralized Logic**: Single navigation utility eliminates code duplication
- **Clean Interfaces**: `NavigationChoice` objects separate data from presentation
- **Consistent Behavior**: Same navigation experience in setup menus, prompts, and all future interfaces
- **Fallback Support**: Automatic detection and graceful degradation for unsupported environments

### Usage Guidelines
**For All CLI Components:**
```python
from src.cli.utils.navigation import ArrowNavigator, NavigationChoice

# Standard choice prompt
navigator = ArrowNavigator()
result = navigator.navigate_choices(prompt, choices, default)

# Full menu interface
menu_items = [NavigationChoice(value, label) for value, label in choices]
result = navigator.navigate_menu(title, menu_items)
```

**Navigation Standards:**
- All interactive CLI elements MUST use the universal navigation system
- Consistent keyboard shortcuts across all interfaces
- Visual highlighting and help system integration required
- Cross-platform compatibility mandatory
- Y/N confirmations use only y/n keys (never numbered options)
- Every option must have descriptive label and status when applicable

## Development Guidelines

### Code Style
- PEP 8 with 100 char line limit
- Async/await for all I/O operations
- Type hints throughout
- Pydantic v2 for validation
- Structured logging with component tracking

### Testing
- **TDD Methodology**: Tests written first
- **200+ Tests**: Contract, integration, unit, performance layers
- **Performance**: <30s installation validation
- **Coverage**: Comprehensive test suite with 100% UV compliance

### Key Patterns
- **Service Architecture**: 50+ services with dependency injection
- **Factory Pattern**: Runtime vector store provider selection
- **Settings Layering**: Global → project → effective configuration
- **Async/Await**: Non-blocking I/O throughout
- **Repository Pattern**: Database abstraction layer

## Performance Metrics
- **Installation**: <30 seconds complete setup
- **System Check**: <5 seconds validation
- **Vector Search**: Sub-second semantic queries
- **Memory**: Chunked processing for large documentation sites
- **Caching**: 5-minute query cache TTL

## Dependencies & Integrations
### Core Dependencies
- **Python 3.13+**, **UV/UVX 0.8+** (package management)
- **FastAPI**, **Click + Rich** (API + CLI)
- **Pydantic v2**, **PyYAML** (data validation)
- **aiosqlite**, **qdrant-client**, **sqlite-vec** (storage)
- **BeautifulSoup4**, **httpx** (web scraping)

### External Services
- **Qdrant**: Production vector database (Docker)
- **Ollama**: Local embeddings (mxbai-embed-large)
- **Docker**: Container management for services

## Crawler Logic Organization

### New Structure (September 2025)
All crawler functionality has been reorganized from scattered `src/services/` and `src/models/` locations into a unified `src/logic/crawler/` structure:

**Core Crawler Components:**
- `src.logic.crawler.core.crawler.DocumentationCrawler` - Main crawler engine
- `src.logic.crawler.core.batch.BatchCrawler` - Multi-project orchestration

**Analytics & Reporting:**
- `src.logic.crawler.analytics.reporter.ErrorReporter` - Error collection and reporting
- `src.logic.crawler.analytics.report.CrawlReport` - Operation results and metrics

**Utilities:**
- `src.logic.crawler.utils.progress.ProgressReporter` - Advanced progress tracking
- `src.logic.crawler.utils.progress.CrawlProgressDisplay` - Simple progress display

**Models:**
- `src.logic.crawler.models.session.CrawlSession` - Session tracking
- `src.logic.crawler.models.page.Page` - Page data structure
- `src.logic.crawler.models.batch.BatchOperation` - Batch operation tracking
- `src.logic.crawler.models.error.ErrorEntry` - Error data structure

### Import Guidelines
**Use new paths:**
```python
from src.logic.crawler.core.crawler import DocumentationCrawler
from src.logic.crawler.analytics.reporter import ErrorReporter
from src.logic.crawler.utils.progress import ProgressReporter
```

**Old paths removed:** All `src.services.crawler*` and related imports have been removed per constitutional guidelines (no backward compatibility).

## Setup Logic Organization

### New Structure (September 2025)
All setup functionality has been reorganized from scattered `src/services/` locations into a unified `src/logic/setup/` structure following service-oriented architecture:

**Core Setup Components:**
- `src.logic.setup.core.orchestrator.SetupOrchestrator` - Main setup coordinator
- `src.logic.setup.core.router.CommandRouter` - Flag routing and validation
- `src.logic.setup.core.menu.InteractiveMenu` - Rich-based interactive UI

**Setup Services:**
- `src.logic.setup.services.initializer.SetupInitializer` - Installation logic
- `src.logic.setup.services.uninstaller.SetupUninstaller` - Clean uninstall
- `src.logic.setup.services.configurator.SetupConfigurator` - Config management
- `src.logic.setup.services.validator.SetupValidator` - System validation
- `src.logic.setup.services.detector.ServiceDetector` - Async service detection
- `src.logic.setup.services.reset_handler.ResetHandler` - Reset operations

**Setup Models:**
- `src.logic.setup.models.operation.SetupOperation` - Operation tracking
- `src.logic.setup.models.configuration.SetupConfiguration` - Setup config
- `src.logic.setup.models.menu_state.MenuState` - Menu navigation state
- `src.logic.setup.models.service_info.ServiceInfo` - External service info
- `src.logic.setup.models.uninstall_manifest.UninstallManifest` - Uninstall planning

**Setup Utilities:**
- `src.logic.setup.utils.progress.ProgressReporter` - Rich progress bars
- `src.logic.setup.utils.prompts` - User interaction helpers

### Setup Import Guidelines
**Use new paths:**
```python
from src.logic.setup.core.orchestrator import SetupOrchestrator
from src.logic.setup.services.initializer import SetupInitializer
from src.logic.setup.utils.progress import ProgressReporter
```

**Unified CLI Command:**
```bash
bablib setup                    # Interactive menu
bablib setup --init --auto      # Quick initialization
bablib setup --uninstall --force # Force uninstall
bablib setup --reset            # Full reset
```

## RAG Logic Organization & Enhancements

### New Structure (September 2025)
All RAG (Retrieval-Augmented Generation) functionality has been reorganized from `src/services/rag.py` into a unified `src/logic/rag/` structure with significant quality and performance improvements.

**Core RAG Components:**
- `src.logic.rag.core.search_service.RAGSearchService` - Enhanced search orchestration (migrated from src/services/rag.py)
- `src.logic.rag.core.chunking_service.ChunkingService` - Document chunking with multiple strategies
- `src.logic.rag.core.reranking_service.RerankingService` - Fast multi-signal reranking (<50ms)

**Strategy Services:**
- `src.logic.rag.strategies.semantic_chunker.SemanticChunker` - Embedding-based semantic chunking
- `src.logic.rag.strategies.query_transformer.QueryTransformer` - Query expansion with synonyms
- `src.logic.rag.strategies.fusion_retrieval.FusionRetrieval` - Reciprocal rank fusion (RRF)

**Analytics Services:**
- `src.logic.rag.analytics.rag_metrics.RAGMetrics` - Performance tracking (latency, cache, usage)
- `src.logic.rag.analytics.quality_metrics.RAGQualityMetrics` - Quality metrics (MRR, precision, recall)

**Utilities:**
- `src.logic.rag.utils.contextual_headers` - Add document context to chunks

**Models:**
- `src.logic.rag.models.chunk.Chunk` - Chunk data structure with hierarchy
- `src.logic.rag.models.search_result.SearchResult` - Search results with rerank scores
- `src.logic.rag.models.strategy_config` - Strategy enums and configuration models

### RAG Import Guidelines
**Use new paths:**
```python
from src.logic.rag.core.search_service import RAGSearchService
from src.logic.rag.core.chunking_service import ChunkingService
from src.logic.rag.core.reranking_service import RerankingService
from src.logic.rag.strategies.semantic_chunker import SemanticChunker
from src.logic.rag.models.strategy_config import SearchStrategy, ChunkStrategy
```

**Deprecated path (with warning):**
```python
# OLD - Still works but shows deprecation warning
from src.services.rag import RAGSearchService

# Deprecation message: "src.services.rag is deprecated and will be removed in a future version.
# Please use src.logic.rag.core.search_service instead."
```

### RAG Phase 1: Quick Wins (Complete)
**Performance Improvements:**
- ✅ **Parallel Sub-Query Execution**: 50-70% latency reduction for advanced search (200ms → <100ms)
- ✅ **Fast Multi-Signal Reranking**: 95% faster reranking (1000ms → <50ms for 10 results)
  - Vector score (0.5 weight)
  - Term overlap (0.3 weight)
  - Title match (0.1 weight)
  - Freshness (0.1 weight)
- ✅ **LRU Embedding Cache**: 10K entry limit (~80MB), prevents memory leaks
- ✅ **Contextual Chunk Headers**: Document title + hierarchy + project prepended to all chunks

**Example:**
```python
# Enhanced search with reranking
results = await rag_service.search(
    query="docker security",
    collection_name="docs",
    strategy=SearchStrategy.ADVANCED,  # Parallel sub-queries
    rerank=True  # Fast multi-signal reranking
)

# Results include rerank scores and signals
for result in results:
    print(f"Score: {result.rerank_score}")
    print(f"Signals: {result.rerank_signals}")  # vector, term, title, freshness
```

### RAG Phase 2: Quality Enhancements (Complete)
**Accuracy Improvements:**
- ✅ **Semantic Chunking**: 15-25% retrieval accuracy improvement
  - Groups sentences by embedding similarity (threshold: 0.75)
  - Respects topic boundaries, no mid-sentence splits
  - Falls back to character chunking on timeout (5s)
- ✅ **Query Transformation**: 15-30% recall improvement
  - Synonym expansion from `~/.config/bablib/query_transformations.yaml`
  - Max 5 query variations executed in parallel
- ✅ **Fusion Retrieval**: 15-25% recall improvement
  - Combines semantic + keyword strategies with RRF (k=60)
  - More robust than single-strategy search

**Example:**
```python
# Semantic chunking during indexing
await rag_service.index_documents(
    collection_name="docs",
    documents=documents,
    chunk_strategy=ChunkStrategy.SEMANTIC,  # Opt-in
    chunk_size=1500
)

# Query transformation with fusion
results = await rag_service.search(
    query="docker setup",
    collection_name="docs",
    strategy=SearchStrategy.FUSION,  # Combines strategies
    transform_query=True  # Expands to 5 variations
)
```

### RAG Phase 3: Production Polish (Complete)
**Monitoring & Optimization:**
- ✅ **RAG Metrics**: Latency tracking (p50, p95, p99), cache hit rate, strategy distribution
- ✅ **Quality Metrics**: MRR, precision@5, recall@10, NDCG@10 tracking
- ✅ **Adaptive Batch Processing**: 10-20% indexing throughput improvement
  - Starts at batch size 50
  - Increases 1.5x on success (max 200)
  - Decreases 0.5x on failure (min 10)

### Performance Targets & Validation
**Constitutional Requirements (All Met):**
- ✅ Reranking: <50ms for 10 results
- ✅ Advanced search: <100ms with parallel queries
- ✅ Indexing: <30s for 100 documents
- ✅ Memory: <500MB total, <80MB cache
- ✅ Quality: Precision@5 ≥0.80, Recall@10 ≥0.70, NDCG@10 ≥0.82

**Test Coverage:**
- 65+ unit tests (cache, headers, models, configs)
- Performance tests for reranking, search, indexing
- Quality test framework with ground truth validation

### Query Transformation Configuration
**Example Synonym Dictionary** (`~/.config/bablib/query_transformations.yaml`):
```yaml
docker: [container, containerization, docker-engine]
install: [setup, installation, deploy, configure]
search: [find, lookup, query, retrieve]
security: [secure, safety, protection, hardening]
```

**50+ built-in synonyms** available in `config/query_transformations.example.yaml`

### Backward Compatibility
**All improvements are opt-in:**
- Default chunking: CHARACTER (existing behavior)
- Default search: SEMANTIC (existing behavior)
- Default reranking: DISABLED (existing behavior)
- Semantic chunking: `--chunk-strategy semantic`
- Query transformation: `--transform-query` flag
- Fusion retrieval: `--strategy fusion`

## Package Integrity & Import Safety

### Critical Development Practice - Root Cause Identified
**UV tool install uses Git committed state, NOT working directory changes!**

**ALWAYS commit changes before testing installation:**
```bash
git add .
git commit -m "Your changes"
uv tool install . --force --reinstall
```

**Root Cause:** UV tool install builds from the last Git commit, ignoring uncommitted changes in your working directory. This means:
- Uncommitted new model files won't be included
- Uncommitted `__init__.py` changes won't be included
- Installation appears to work but uses stale code

### When to commit before installing:
- After adding new model files
- After modifying `__init__.py` files
- After changing package structure
- Before testing `uv tool install`
- When encountering import errors

### Verification Script (Emergency Only)
For urgent debugging only, use:
```bash
./.verify-package.sh
```

**Primary Rule:** Always commit first, then install. This prevents 99% of import issues.

## Important Instructions
- ALWAYS check constitution.md before working on any features or making changes
- ALWAYS reference .specify/memory/constitution.md for core architectural principles
- ALWAYS reference .specify/memory/dependencies.md for version constraints and justifications
- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested

## Core Reference Documents
- **Constitution**: `.specify/memory/constitution.md` - Core principles and architectural standards
- **Dependencies**: `.specify/memory/dependencies.md` - All package versions with justifications
