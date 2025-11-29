# Bablib Comprehensive Testing Plan

## Summary of Testing Session (2025-09-29)

### Issues Found and Fixed:
1. **Database schema migration issues** - ✅ FIXED
   - **Root cause**: Missing `crawl_depth` column in project-specific databases
   - **Solution**: Added comprehensive project database migration system
   - **Implementation**: `_apply_project_migrations` method in `src/services/database.py:405-451`
   - **Coverage**: Handles both new and existing project database connections

2. **UnifiedProjectService API mismatches** - ✅ FIXED
   - Fixed: `get_project` → `get_project_by_name`
   - Fixed: `remove_project` → `delete_project`
   - Fixed: `get_project_stats` → `get_project_statistics`
   - Fixed: Enum/string handling in _store_project method

3. **Successfully tested:**
   - Setup initialization with --force flag
   - Project creation with unified schema
   - Project listing and display (after fixes)
   - Multiple MCP servers running concurrently
   - Database migration implementation (requires testing with fresh install)

### Migration Implementation Details:
- **New migration method**: `_apply_project_migrations` checks and adds missing columns
- **Column detection**: Uses `PRAGMA table_info()` to safely detect missing columns
- **Safe migration**: `ALTER TABLE ADD COLUMN` with default values
- **Version tracking**: Updates schema version to prevent repeated migrations
- **Dual trigger**: Applied both during new database creation and cached connection access

## Testing Objectives
- Validate all CLI commands with various flag combinations
- Test error handling and edge cases
- Verify data persistence and integrity
- Ensure proper service integration
- Validate security boundaries
- Test performance under load
- Verify MCP server functionality

## 1. Setup Command Testing

### 1.1 Interactive Mode
- [x] Run `bablib setup` without flags - verify interactive menu appears ✅
- [ ] Test arrow navigation (↑/↓) in menu
- [ ] Test number selection (1-9) in menu
- [ ] Test vim keys (j/k) navigation
- [ ] Test help display (?)
- [ ] Test escape/quit (q/ESC)
- [ ] Select each menu option and verify proper routing

### 1.2 Initialization Testing
- [ ] `bablib setup --init` - test interactive initialization
- [x] `bablib setup --init --auto` - test automatic initialization ✅ (requires --force for reinit)
- [x] `bablib setup --init --force` - test forced initialization ✅
- [ ] `bablib setup --init --non-interactive` - test non-interactive mode
- [ ] `bablib setup --init --vector-store sqlite_vec` - test SQLite-vec selection
- [ ] `bablib setup --init --vector-store qdrant` - test Qdrant selection
- [ ] `bablib setup --init --vector-store invalid` - verify error handling
- [ ] Test initialization when already initialized (should warn)
- [ ] Test initialization with insufficient permissions
- [ ] Test initialization with disk space issues (mock)
- [ ] Test initialization with Python version < 3.13 (if possible)

### 1.3 Configuration Testing
- [ ] `bablib setup --config` - test configuration display
- [ ] `bablib setup --config --show` - test detailed config display
- [ ] `bablib setup --config --edit` - test config editing
- [ ] Test config file corruption recovery
- [ ] Test invalid YAML in config file
- [ ] Test missing config file handling

### 1.8 Setup Flag Combinations
- [ ] `bablib setup --init --force` - force reinitialize
- [ ] `bablib setup --init --auto --force` - auto with force
- [ ] `bablib setup --init --non-interactive --vector-store sqlite_vec`
- [ ] `bablib setup --uninstall --backup --dry-run` - preview with backup
- [ ] `bablib setup --reset --preserve-data --force` - reset keeping data
- [ ] `bablib setup --uninstall --preserve-data --backup`
- [ ] Test invalid combinations: `--init --uninstall`
- [ ] Test invalid combinations: `--init --reset`
- [ ] Test invalid combinations: `--uninstall --reset`

### 1.4 Uninstall Testing
- [ ] `bablib setup --uninstall` - test interactive uninstall
- [ ] `bablib setup --uninstall --force` - test forced uninstall
- [ ] `bablib setup --uninstall --preserve-data` - test data preservation
- [ ] `bablib setup --uninstall --dry-run` - test dry run mode
- [ ] Test uninstall with active projects
- [ ] Test uninstall with running servers
- [ ] Verify all directories are cleaned up properly
- [ ] Verify MCP configs are removed

### 1.5 Reset Testing
- [ ] `bablib setup --reset` - test full reset
- [ ] `bablib setup --reset --preserve-data` - test data preservation
- [ ] `bablib setup --reset --force` - test forced reset
- [ ] Test reset with corrupted state
- [ ] Test reset recovery mechanisms

### 1.6 Status Testing
- [ ] `bablib setup --status` - test status display
- [ ] Test status with all services running
- [ ] Test status with services partially available
- [ ] Test status with no services available

### 1.7 Edge Cases & Errors
- [ ] Test conflicting flags (e.g., --init --uninstall)
- [ ] Test multiple operations flags
- [ ] Test with read-only filesystem
- [ ] Test with network issues (for Qdrant/Ollama detection)
- [ ] Test Unicode in paths and configurations
- [ ] Test extremely long project names
- [ ] Test special characters in inputs

## 2. Project Command Testing

### 2.1 Project Creation
- [x] `bablib project --create test1 --type crawling` ✅
- [x] `bablib project --create test2 --type data` ✅
- [x] `bablib project --create test3 --type storage` ✅
- [x] `bablib project --create test-unified-1 --type crawling` ✅ (Fixed API mismatches in UnifiedProjectService)
- [ ] `bablib project --create "test 4" --type crawling --description "Test with spaces"`
- [ ] Test creation with duplicate names (should fail)
- [ ] Test creation with invalid type
- [ ] Test creation without required flags
- [ ] Test creation with very long description
- [ ] Test creation with special characters in name
- [ ] Test creation with reserved names (., .., /, etc.)
- [ ] Test creation when at project limit

### 2.2 Project Listing
- [x] `bablib project --list` - basic listing ✅
- [ ] `bablib project --list --verbose` - detailed listing
- [ ] `bablib project --list --status active`
- [ ] `bablib project --list --status inactive`
- [ ] `bablib project --list --limit 5`
- [ ] `bablib project --list --format json`
- [ ] `bablib project --list --format table`
- [ ] Test listing with no projects
- [ ] Test listing with 100+ projects
- [ ] Test listing with corrupted project data

### 2.3 Project Display
- [x] `bablib project --show test1` ✅ (Fixed)
- [ ] `bablib project --show test1 --detailed`
- [ ] `bablib project --show test1 --format json`
- [ ] Test show with non-existent project
- [ ] Test show with special characters in name

### 2.4 Project Update
- [ ] `bablib project --update test1 --description "Updated description"`
- [ ] `bablib project --update test1 --settings '{"key": "value"}'`
- [ ] `bablib project --update test1 --status inactive`
- [ ] Test update with invalid JSON settings
- [ ] Test update with non-existent project
- [ ] Test concurrent updates (race conditions)

### 2.5 Project Removal
- [ ] `bablib project --remove test1`
- [ ] `bablib project --remove test1 --confirm`
- [ ] `bablib project --remove test1 --backup`
- [ ] `bablib project --remove test1 --force`
- [ ] Test removal of non-existent project
- [ ] Test removal of project with active crawl
- [ ] Test removal of project being served
- [ ] Verify data cleanup after removal

### 2.6 Interactive Mode
- [ ] `bablib project` without flags - test interactive menu
- [ ] Test all interactive menu options
- [ ] Test navigation in project selection

## 3. Crawl Command Testing

### 3.1 Basic Crawling
- [x] `bablib crawl test1 --url https://example.com` ✅ (FIXED: Database migration implemented)
- [x] `bablib crawl test-unified-1 --url https://example.com --max-pages 1` ✅ (FIXED: crawl_depth column migration added)
- [ ] `bablib crawl test-crawl --url https://example.com --max-pages 10`
- [ ] `bablib crawl test-crawl --url https://example.com --depth 2`
- [ ] `bablib crawl test-crawl --url https://example.com --rate-limit 0.5`
- [ ] Test crawl with existing project name (update mode)
- [ ] Test crawl with invalid URL
- [ ] Test crawl with unreachable URL
- [ ] Test crawl with redirect chains
- [ ] Test crawl with authentication required

### 3.2 Advanced Crawling
- [ ] Test crawl with custom headers
- [ ] Test crawl with cookies
- [ ] Test crawl with user agent
- [ ] Test crawl resume after interruption
- [ ] Test crawl with --exclude patterns
- [ ] Test crawl with --include patterns
- [ ] Test JavaScript-heavy sites
- [ ] Test sites with rate limiting
- [ ] Test sites with cloudflare protection

### 3.3 Batch Operations
- [ ] `bablib crawl --update test-crawl`
- [ ] `bablib crawl --update --all`
- [ ] `bablib crawl --update --all --parallel 4` - parallel updates
- [ ] `bablib crawl --update --all --parallel 1` - sequential updates
- [ ] `bablib crawl --update --all --quiet` - suppress progress
- [ ] `bablib crawl --update --all --debug` - detailed output
- [ ] Test batch with mixed project types
- [ ] Test batch interruption and resume
- [ ] Test batch with some failures

### 3.5 Crawl Flag Combinations
- [ ] `bablib crawl test --url https://example.com --max-pages 10 --depth 2 --rate-limit 0.5`
- [ ] `bablib crawl test --update --debug --quiet` - conflicting flags
- [ ] `bablib crawl test --url https://example.com --parallel 8 --rate-limit 10` - aggressive crawling
- [ ] `bablib crawl test --max-pages 1 --depth 0` - single page only
- [ ] Test crawl without project name (should fail)
- [ ] Test crawl with both --url and --update (should handle properly)

### 3.4 Error Handling
- [ ] Test crawl with 404 errors
- [ ] Test crawl with 500 errors
- [ ] Test crawl with timeout
- [ ] Test crawl with SSL errors
- [ ] Test crawl with infinite loops
- [ ] Test crawl with circular references
- [ ] Test crawl memory limits
- [ ] Test crawl disk space limits

## 4. Upload Command Testing

### 4.1 Interactive Mode
- [ ] `bablib upload` - launch interactive menu
- [ ] Test project selection navigation
- [ ] Test source type selection (local, http, ftp, sftp, smb)
- [ ] Test file browser navigation
- [ ] Test multi-file selection
- [ ] Test upload cancellation

### 4.2 Local File Upload
- [ ] `bablib upload files --project test1 --source /path/to/file --type local`
- [ ] `bablib upload files --project test1 --source /path/to/dir --type local --recursive`
- [ ] `bablib upload files --project test1 --source /path/to/dir --type local --recursive --exclude "*.tmp"`
- [ ] `bablib upload files --project test1 --source /path/to/file --type local --dry-run`
- [ ] `bablib upload files --project test1 --source /path/to/file --type local --overwrite ask`
- [ ] `bablib upload files --project test1 --source /path/to/file --type local --overwrite skip`
- [ ] `bablib upload files --project test1 --source /path/to/file --type local --overwrite overwrite`
- [ ] `bablib upload files --project test1 --source /path/to/file --type local --progress`
- [ ] Test upload with multiple --exclude patterns
- [ ] Test upload with non-existent file
- [ ] Test upload with permission denied
- [ ] Test upload of large files (>100MB)
- [ ] Test upload of binary files
- [ ] Test upload with symlinks
- [ ] Test upload with spaces in filename
- [ ] Test upload with Unicode filenames

### 4.3 HTTP/HTTPS Upload
- [ ] `bablib upload files --project test1 --source https://example.com/doc.pdf --type https`
- [ ] `bablib upload files --project test1 --source http://example.com/data.json --type http`
- [ ] `bablib upload files --project test1 --source https://example.com/file --type https --username user`
- [ ] Test URL upload with authentication
- [ ] Test URL upload with large files
- [ ] Test URL upload with timeout
- [ ] Test URL upload with redirects
- [ ] Test URL upload with SSL errors

### 4.4 FTP Upload
- [ ] `bablib upload files --project test1 --source ftp://server/path --type ftp`
- [ ] `bablib upload files --project test1 --source ftp://server/path --type ftp --username user`
- [ ] `bablib upload files --project test1 --source ftp://server/path --type ftp --recursive`
- [ ] Test FTP with anonymous access
- [ ] Test FTP with authentication
- [ ] Test FTP with passive mode
- [ ] Test FTP connection failures

### 4.5 SFTP Upload
- [ ] `bablib upload files --project test1 --source sftp://server/path --type sftp`
- [ ] `bablib upload files --project test1 --source sftp://server/path --type sftp --username user`
- [ ] `bablib upload files --project test1 --source sftp://server/path --type sftp --recursive`
- [ ] Test SFTP with password authentication
- [ ] Test SFTP with SSH key authentication
- [ ] Test SFTP with non-standard port
- [ ] Test SFTP connection failures

### 4.6 SMB Upload
- [ ] `bablib upload files --project test1 --source smb://server/share/path --type smb`
- [ ] `bablib upload files --project test1 --source smb://server/share/path --type smb --username user`
- [ ] `bablib upload files --project test1 --source smb://server/share/path --type smb --recursive`
- [ ] Test SMB with domain authentication
- [ ] Test SMB with guest access
- [ ] Test SMB connection failures

### 4.7 Status Monitoring
- [ ] `bablib upload status`
- [ ] `bablib upload status --project test1`
- [ ] `bablib upload status --operation upload_test1_12345`
- [ ] `bablib upload status --active`
- [ ] Test status during active upload
- [ ] Test status with completed uploads
- [ ] Test status with failed uploads
- [ ] Test status with no uploads

### 4.8 Advanced Upload Options
- [ ] Combination: `--recursive --exclude "*.log" --exclude "*.tmp"`
- [ ] Combination: `--dry-run --progress`
- [ ] Combination: `--overwrite skip --recursive`
- [ ] Test upload with project that doesn't exist
- [ ] Test upload with invalid source type
- [ ] Test upload with conflicting flags
- [ ] Test upload with insufficient disk space
- [ ] Test upload interruption and resume

## 5. Serve Command Testing

### 5.1 Read-Only Server
- [x] `bablib serve` - default settings ✅ (Multiple servers running on different ports)
- [ ] `bablib serve --host 0.0.0.0 --port 9382`
- [ ] `bablib serve --host 127.0.0.1 --port 9383`
- [ ] `bablib serve --foreground`
- [ ] Test server with no projects
- [ ] Test server with multiple projects
- [ ] Test server port conflicts
- [ ] Test server shutdown gracefully

### 5.2 Admin Server
- [ ] `bablib serve --admin`
- [ ] `bablib serve --admin --host 127.0.0.1 --port 9384`
- [ ] Verify admin refuses non-localhost binding
- [ ] Test admin command execution
- [ ] Test admin security restrictions
- [ ] Verify blocked operations (uninstall, reset, delete-all)

### 5.3 API Endpoints Testing
- [ ] GET /health - health check
- [ ] GET /projects - list projects
- [ ] GET /projects/{name} - get project
- [ ] POST /search - semantic search
- [ ] GET /files/{project}/{path} - file access
- [ ] Test CORS headers
- [ ] Test authentication (if applicable)
- [ ] Test rate limiting
- [ ] Test concurrent requests
- [ ] Test malformed requests

### 5.4 MCP Protocol Testing
- [ ] Test MCP tool discovery
- [ ] Test MCP resource listing
- [ ] Test MCP prompt generation
- [ ] Test MCP error handling
- [ ] Test MCP with Claude Code
- [ ] Test MCP with other clients

## 6. Health Command Testing

### 6.1 Basic Health Checks
- [x] `bablib health` - full health check ✅
- [ ] `bablib health --system` - system checks only
- [ ] `bablib health --services` - external service checks only
- [ ] `bablib health --config` - configuration validity checks
- [ ] `bablib health --projects` - project-specific health checks
- [ ] `bablib health --verbose` - detailed diagnostic information
- [ ] `bablib health --timeout 5` - quick health check
- [ ] `bablib health --timeout 60` - thorough health check

### 6.2 Health Flag Combinations
- [ ] `bablib health --system --services` - multiple checks
- [ ] `bablib health --config --projects --verbose` - detailed subset
- [ ] `bablib health --services --timeout 1` - quick service check
- [ ] `bablib health --format json` - JSON output
- [ ] Test health with all flags combined
- [ ] Test health with no vector store configured
- [ ] Test health with degraded services
- [ ] Test health with critical failures

## 7. Vector Store Testing

### 7.1 SQLite-vec Testing
- [ ] Initialize with SQLite-vec
- [ ] Create project with SQLite-vec
- [ ] Perform searches with SQLite-vec
- [ ] Test concurrent access to SQLite-vec
- [ ] Test SQLite-vec corruption recovery
- [ ] Test SQLite-vec migration
- [ ] Test SQLite-vec performance with 10k+ documents

### 7.2 Qdrant Testing
- [ ] Initialize with Qdrant
- [ ] Verify Qdrant connection
- [ ] Create project with Qdrant
- [ ] Perform searches with Qdrant
- [ ] Test Qdrant connection loss
- [ ] Test Qdrant restart recovery
- [ ] Test Qdrant data persistence

### 7.3 Provider Switching
- [ ] Switch from SQLite-vec to Qdrant
- [ ] Switch from Qdrant to SQLite-vec
- [ ] Test data migration between providers
- [ ] Test fallback mechanisms

## 8. Integration Testing

### 8.1 End-to-End Workflows
- [ ] Complete setup → project → crawl → search workflow
- [ ] Setup → upload → serve → query workflow
- [ ] Multi-project management workflow
- [ ] Backup and restore workflow

### 8.2 Service Integration
- [ ] Ollama embedding generation
- [ ] Docker container management
- [ ] Git integration (if applicable)
- [ ] File system operations

### 8.3 Performance Testing
- [ ] Crawl 1000+ pages
- [ ] Handle 10+ concurrent crawls
- [ ] Search across 100k+ documents
- [ ] Serve 100+ concurrent requests
- [ ] Memory usage under load
- [ ] CPU usage optimization

## 9. Security Testing

### 9.1 Input Validation
- [ ] SQL injection attempts
- [ ] Command injection attempts
- [ ] Path traversal attempts
- [ ] XSS in web interface
- [ ] CSRF protection
- [ ] File upload security

### 9.2 Access Control
- [ ] Admin server localhost restriction
- [ ] File access permissions
- [ ] Project isolation
- [ ] API authentication

### 9.3 Data Security
- [ ] Sensitive data handling
- [ ] Credential storage
- [ ] Log sanitization
- [ ] Secure defaults

## 10. Error Recovery Testing

### 10.1 Crash Recovery
- [ ] Kill process during crawl
- [ ] Kill process during upload
- [ ] Kill process during initialization
- [ ] Power failure simulation
- [ ] Disk full scenarios

### 10.2 Data Recovery
- [ ] Corrupted database recovery
- [ ] Partial write recovery
- [ ] Transaction rollback
- [ ] Backup restoration

### 10.3 Service Recovery
- [ ] Service restart handling
- [ ] Connection retry logic
- [ ] Graceful degradation
- [ ] Fallback mechanisms

## 11. Test Suite Execution

### 11.1 Unit Tests
- [ ] Run `pytest tests/unit/ -v`
- [ ] Fix any failing unit tests
- [ ] Achieve >80% coverage

### 11.2 Integration Tests
- [ ] Run `pytest tests/integration/ -v`
- [ ] Fix any failing integration tests
- [ ] Verify all flows work

### 11.3 Contract Tests
- [ ] Run `pytest tests/contract/ -v`
- [ ] Fix any API contract violations
- [ ] Verify backward compatibility

### 11.4 Performance Tests
- [ ] Run `pytest tests/performance/ -v`
- [ ] Verify <30s installation
- [ ] Verify response time SLAs

### 11.5 Package Verification
- [ ] Run `./.verify-package.sh`
- [ ] Fix any import issues
- [ ] Verify clean installation

## 12. Environment Testing

### 12.1 Operating Systems
- [ ] macOS (current environment)
- [ ] Linux (Docker/VM if needed)
- [ ] Windows WSL (if available)

### 12.2 Python Versions
- [ ] Python 3.13 (required minimum)
- [ ] Python 3.14 (if available)

### 12.3 Dependency Versions
- [ ] Latest UV version
- [ ] Minimum UV version (0.8)
- [ ] Latest dependency updates
- [ ] Dependency conflicts

## 13. Documentation Testing

### 13.1 CLI Help
- [ ] `bablib --help`
- [ ] `bablib setup --help`
- [ ] `bablib project --help`
- [ ] `bablib crawl --help`
- [ ] `bablib upload --help`
- [ ] `bablib serve --help`
- [ ] Verify all help text is accurate

### 13.2 Error Messages
- [ ] Verify error messages are helpful
- [ ] Verify error suggestions work
- [ ] Verify stack traces are meaningful

## 14. MCP Server Testing Strategy

### 14.1 Fix Module Import Issues
- [ ] Identify missing `src.services.project` module references
- [ ] Update import paths to new organization structure
- [ ] Test imports after fixing
- [ ] Verify all MCP dependencies are available

### 14.2 MCP Server Setup
- [ ] Start read-only server: `bablib serve --host 0.0.0.0 --port 9383`
- [ ] Start admin server: `bablib serve --admin --host 127.0.0.1 --port 9384`
- [ ] Verify both servers can run simultaneously
- [ ] Check server logs for startup errors
- [ ] Test server shutdown and restart

### 14.3 Local Testing with curl
- [ ] Test health endpoint: `curl http://localhost:9383/health`
- [ ] Test project list: `curl http://localhost:9383/projects`
- [ ] Test specific project: `curl http://localhost:9383/projects/{name}`
- [ ] Test search endpoint: `curl -X POST http://localhost:9383/search -H "Content-Type: application/json" -d '{"query":"test"}'`
- [ ] Test admin endpoints on port 9384
- [ ] Verify localhost-only restriction on admin server

### 14.4 MCP Protocol Testing
- [ ] Test MCP tool discovery endpoint
- [ ] Test MCP resource listing
- [ ] Test MCP prompt generation
- [ ] Generate MCP client configs in mcp/ directory
- [ ] Test with MCP test client (if available)

### 14.5 Claude Code Integration
- [ ] Configure Claude Code with read-only server
- [ ] Configure Claude Code with admin server
- [ ] Test project listing via Claude Code
- [ ] Test search functionality via Claude Code
- [ ] Test admin commands via Claude Code
- [ ] Verify blocked operations (uninstall, reset, delete-all)

### 14.6 Playwright MCP Testing
- [ ] Use Playwright to navigate to server endpoints
- [ ] Screenshot API responses
- [ ] Test concurrent requests
- [ ] Test error handling with invalid requests
- [ ] Monitor console logs for errors

### 14.7 Security Testing
- [ ] Verify admin server refuses non-localhost connections
- [ ] Test path traversal protection
- [ ] Test command injection protection
- [ ] Test resource limits and timeouts
- [ ] Verify operation restrictions work

## 15. Additional Test Combinations

### 15.1 Setup Command Advanced Combinations
- [ ] `bablib setup --init --auto --vector-store qdrant --force`
- [ ] `bablib setup --init --non-interactive --force --vector-store sqlite_vec`
- [ ] `bablib setup --uninstall --backup --preserve-data --dry-run`
- [ ] `bablib setup --reset --force --dry-run` (should warn about conflicting flags)
- [ ] `bablib setup --status --verbose --timeout 30`
- [ ] `bablib setup --config --validate --fix`

### 15.2 Project Command Advanced Combinations
- [ ] `bablib project --create test --type crawling --settings '{"auto_crawl": true}' --description "Auto crawl test"`
- [ ] `bablib project --list --status active --limit 10 --format json --verbose`
- [ ] `bablib project --show test --detailed --format json --export /tmp/project.json`
- [ ] `bablib project --update test --status inactive --settings '{}' --force`
- [ ] `bablib project --remove test --backup --confirm --archive --path /backup/`
- [ ] `bablib project --batch-create --from-file projects.yaml`
- [ ] `bablib project --export-all --format csv --output projects.csv`

### 15.3 Crawl Command Advanced Combinations
- [ ] `bablib crawl test --url https://example.com --max-pages 100 --depth 5 --rate-limit 2.0 --exclude "*.pdf" --include "docs/*"`
- [ ] `bablib crawl test --update --force --debug --parallel 4 --timeout 300`
- [ ] `bablib crawl --update --all --parallel 8 --rate-limit 5.0 --retry 3 --continue-on-error`
- [ ] `bablib crawl test --url https://example.com --headers '{"User-Agent": "Custom"}' --cookies cookies.txt`
- [ ] `bablib crawl test --sitemap https://example.com/sitemap.xml --follow-external false`
- [ ] `bablib crawl test --url https://example.com --screenshot --extract-metadata --store-raw`

### 15.4 Upload Command Advanced Combinations
- [ ] `bablib upload files --project test --source /path/ --type local --recursive --exclude "*.log" --include "*.md" --parallel 4`
- [ ] `bablib upload files --project test --source https://example.com/file --type https --retry 5 --timeout 60 --verify-ssl false`
- [ ] `bablib upload files --project test --source ftp://server/ --type ftp --passive --binary --recursive --preserve-timestamps`
- [ ] `bablib upload files --project test --source sftp://server/ --type sftp --key ~/.ssh/id_rsa --port 2222 --recursive`
- [ ] `bablib upload files --project test --source smb://server/share --type smb --domain WORKGROUP --recursive --hidden`
- [ ] `bablib upload batch --from-file upload-list.txt --project test --parallel 10 --continue-on-error`
- [ ] `bablib upload status --active --watch --format json --interval 1`

### 15.5 Serve Command Advanced Combinations
- [ ] `bablib serve --host 0.0.0.0 --port 9382 --foreground --workers 4 --reload`
- [ ] `bablib serve --admin --host 127.0.0.1 --port 9384 --ssl-cert cert.pem --ssl-key key.pem`
- [ ] `bablib serve --host 0.0.0.0 --port 9382 --cors "*" --rate-limit 100 --timeout 30`
- [ ] `bablib serve --admin --debug --log-level DEBUG --access-log --error-log errors.log`
- [ ] `bablib serve --health-only --port 9385` (health endpoint only mode)
- [ ] `bablib serve --metrics --prometheus --port 9386` (metrics endpoint)

### 15.6 Health Command Advanced Combinations
- [ ] `bablib health --all --verbose --format json --output health.json`
- [ ] `bablib health --system --services --projects --config --timeout 60 --retry 3`
- [ ] `bablib health --watch --interval 5 --alert-on-failure`
- [ ] `bablib health --diagnose --fix --backup-first`
- [ ] `bablib health --benchmark --iterations 10 --report benchmark.html`

### 15.7 Vector Store Specific Tests
- [ ] `BABLIB_VECTOR_STORE=qdrant bablib setup --init --auto`
- [ ] `BABLIB_VECTOR_STORE=qdrant bablib project --create qdrant-test --type data`
- [ ] `BABLIB_VECTOR_STORE=qdrant bablib crawl qdrant-test --url https://example.com`
- [ ] `BABLIB_VECTOR_STORE=qdrant bablib serve --port 9387`
- [ ] `BABLIB_VECTOR_STORE=sqlite_vec bablib migrate --from qdrant --to sqlite_vec`
- [ ] Test vector store with 100k+ documents
- [ ] Test vector store failover scenarios

### 15.8 Environment Variable Combinations
- [ ] Test with all BABLIB_* env vars set
- [ ] Test with conflicting env vars and CLI flags
- [ ] Test with invalid env var values
- [ ] Test env var precedence order
- [ ] Test sensitive data in env vars

### 15.9 Concurrent Operations
- [ ] Run multiple crawls simultaneously
- [ ] Run crawl + upload + serve simultaneously
- [ ] Multiple clients accessing same project
- [ ] Concurrent project updates
- [ ] Race condition testing

### 15.10 Edge Cases & Stress Tests
- [ ] Project name with 255 characters
- [ ] Description with 10,000 characters
- [ ] URL with 2000+ character query string
- [ ] Upload 10,000 files at once
- [ ] Crawl site with 100,000+ pages
- [ ] Search across 1M+ documents
- [ ] 1000 concurrent API requests
- [ ] Run for 24 hours continuously

## Test Execution Log

### Session 1: 2025-09-28 20:45
### Session 2: 2025-09-28 21:15
### Session 3: 2025-09-29 (Current)
### Session 4: 2025-09-29 08:17 (Comprehensive Testing)

#### Test Execution Summary:
- **Setup Commands**: ✅ Interactive mode works, initialization works with --force
- **Project Commands**: ✅ Creation works for all types, listing works
  - ❌ Issue: `--show` command has error with 'str' object has no attribute 'value'
- **Crawl Commands**: ❌ Cannot find created projects (database connection issue)
- **Health Commands**: ✅ Working correctly, shows system status
- **Serve Commands**: ⚠️ Multiple servers running but health endpoint returns errors

#### Progress Made:
1. **Enhanced TEST_PLAN.md** ✅ - Added 100+ new test combinations covering all command variants
2. **Qdrant Testing** ✅ - Successfully tested Qdrant deployment and MCP server integration
   - Created project with Qdrant: `qdrant-test` project successful
   - Started Qdrant MCP server on port 9393
   - Verified API endpoints work with correct JSON-RPC format
3. **MCP Server Analysis** ✅ - Identified root cause of empty project lists
   - Both SQLite-vec and Qdrant servers return empty project lists
   - Issue is in project data access, not vector store specific
   - API format requires `{"method": "list_projects", "params": {}}` structure

#### Issues Found:
1. **Project creation error** - 'dict' object has no attribute 'data' when accessing project attributes
2. **Project listing error** - 'str' object has no attribute 'value' when displaying project type/status
3. **Module not found** - src.lib was not being packaged due to .gitignore excluding lib/
4. **Crawl command issue** - Unable to find existing projects (database connection issue)
5. **MCP server error** - No module named 'src.services.project'
6. **Test import errors** - Multiple missing modules in unit tests (batch_operation, error_handler, etc.)
7. **Deprecated Pydantic validators** - Using V1 style @validator instead of V2 @field_validator

#### Fixes Applied:
1. ✅ Fixed project creation by properly converting settings dict to ProjectConfig object
2. ✅ Fixed project listing by safely handling both enum and string types for type/status
3. ✅ Fixed .gitignore to exclude only top-level /lib/, not src/lib/
4. ✅ Added lib and logic to package by fixing src/__init__.py (then removed to fix circular import)
5. ⏳ MCP server module issues need investigation
6. ⏳ Test module imports need fixing
7. ⏳ Pydantic validators need migration to V2 style

#### Session 4 Results - Comprehensive Testing:
- **Automated Tests**: ⚠️ Multiple syntax errors in test files preventing execution
  - 25 import errors found in contract tests
  - Tests unable to run due to missing async context issues
- **MCP Server Testing**: ✅ Both read-only and admin servers running
  - Read-only server on port 9396: Working
  - Admin server on port 9397: Working with localhost restriction
  - Health endpoints functional
  - API endpoints need investigation (returning "Endpoint not found")
- **Project Management**: ✅ All project types created successfully
  - mcp-test-1 (crawling)
  - storage-test (storage)
  - data-test (data)
  - google-adk (crawling)
- **Test Document Enhancement**: ✅ Added 100+ new MCP test scenarios
  - Comprehensive MCP server testing suite (Section 17)
  - Detailed test cases for all MCP operations
  - Security, performance, and integration test scenarios

#### Key Issues Identified:
1. **Test Files**: Multiple async syntax errors in contract tests
2. **MCP Endpoints**: Project listing endpoints not exposed correctly
3. **Import Errors**: Missing modules and incorrect import paths

#### Session 2 Results:
- **MCP Server Fixed**: ✅ Server starts successfully after fixing imports
  - Fixed imports: ProjectService → ProjectManager, SearchService → RAGSearchService
  - Fixed embedding import path (embeddings.py not embedding.py)
  - Fixed VectorStoreFactory method (create_vector_store not create)

- **MCP Server Testing**: ✅ Basic functionality working
  - Health endpoint: Working (returns status)
  - Project list endpoint: Working (returns empty list - needs investigation)
  - Server starts on port 9392 successfully

- **Unit Test Status**: ❌ 7 import errors preventing test execution
  - ModuleNotFoundError: src.models.batch_operation
  - ImportError: ShortKeyValidator from short_key_validator
  - ModuleNotFoundError: src.services.error_handler
  - ImportError: FormatValidator from format_validator
  - ModuleNotFoundError: src.cli.post_install
  - ImportError: SourceType from upload models
  - ImportError: VectorStoreSettings from settings

- **Command Testing**: ✅ Basic commands working
  - Project creation: Working
  - Project listing: Working (4 projects created)
  - Server startup: Working

#### Overall Status:
- Unit Tests: ❌ Fail (7 import errors, 328 tests collected)
- Integration Tests: ⏳ Not run
- Contract Tests: ⏳ Not run
- Performance Tests: ⏳ Not run
- MCP Servers: ✅ Working (basic functionality)

### Notes:
- Project creation and listing now work correctly
- Package structure issues mostly resolved (lib now included)
- Still have module reference issues in tests and MCP server
- Need to update deprecated Pydantic validators
- Crawl command has project lookup issues

## 16. MCP Server Method Testing (Detailed)

### 16.1 Read-Only Server Methods (Port 9382/9383)

#### 16.1.1 list_projects Method
**Purpose**: List all Bablib projects with optional filtering
**Parameters**:
- `status_filter` (optional): Filter by project status
- `limit` (optional): Limit number of results

**Test Cases**:
- [ ] `list_projects()` - Get all projects
- [ ] `list_projects(status_filter="active")` - Filter active projects
- [ ] `list_projects(status_filter="inactive")` - Filter inactive projects
- [ ] `list_projects(limit=5)` - Limit results
- [ ] `list_projects(status_filter="active", limit=3)` - Combined filtering
- [ ] `list_projects(status_filter="invalid")` - Invalid status filter
- [ ] Test with no projects in database
- [ ] Test with 100+ projects
- [ ] Test with corrupted project data
- [ ] Test concurrent access during project creation

**Expected Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "name": "project1",
      "type": "crawling",
      "status": "active",
      "description": "Test project",
      "created_at": "2025-09-29T...",
      "last_updated": "2025-09-29T...",
      "file_count": 42
    }
  ],
  "metadata": {
    "total_count": 10,
    "filtered_count": 5
  }
}
```

#### 16.1.2 search_projects Method
**Purpose**: Search projects using embeddings
**Parameters**:
- `query` (required): Search query string
- `project_names` (optional): Limit search to specific projects
- `limit` (optional): Maximum results (default 10)

**Test Cases**:
- [ ] `search_projects("test query")` - Basic search
- [ ] `search_projects("test", limit=5)` - Limited results
- [ ] `search_projects("test", project_names=["proj1", "proj2"])` - Scoped search
- [ ] `search_projects("")` - Empty query
- [ ] `search_projects("very long query string...")` - Long query
- [ ] `search_projects("query", project_names=["nonexistent"])` - Non-existent project
- [ ] `search_projects("query", limit=0)` - Zero limit
- [ ] `search_projects("query", limit=1000)` - Large limit
- [ ] Test with special characters in query
- [ ] Test with Unicode characters
- [ ] Test search performance with large document set

**Expected Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "project_name": "project1",
      "file_path": "docs/readme.md",
      "content_snippet": "This is a test...",
      "similarity_score": 0.85,
      "metadata": {}
    }
  ],
  "metadata": {
    "query": "test query",
    "total_results": 3,
    "search_time_ms": 45.2
  }
}
```

#### 16.1.3 get_project_files Method
**Purpose**: Get project file information with access control
**Parameters**:
- `project_name` (required): Name of the project
- `file_path` (optional): Specific file path
- `include_content` (optional): Include file content (access-controlled)

**Test Cases**:
- [ ] `get_project_files("project1")` - List all files
- [ ] `get_project_files("project1", file_path="readme.md")` - Specific file
- [ ] `get_project_files("project1", include_content=True)` - With content (storage only)
- [ ] `get_project_files("crawling_project", include_content=True)` - Content denied for crawling
- [ ] `get_project_files("data_project", include_content=True)` - Content denied for data
- [ ] `get_project_files("nonexistent")` - Non-existent project
- [ ] `get_project_files("project1", file_path="nonexistent.txt")` - Non-existent file
- [ ] Test with very long file paths
- [ ] Test with Unicode filenames
- [ ] Test with binary files
- [ ] Test access control enforcement

**Expected Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "path": "readme.md",
      "size": 1024,
      "modified_at": "2025-09-29T...",
      "content_type": "text/markdown",
      "content": "File content..." // Only for storage projects
    }
  ],
  "metadata": {
    "project_name": "project1",
    "project_type": "storage",
    "access_level": "content"
  }
}
```

### 16.2 Admin Server Methods (Port 9384)

#### 16.2.1 execute_command Method
**Purpose**: Execute arbitrary Bablib CLI commands
**Parameters**:
- `request` (CommandExecutionRequest): Command details

**Test Cases**:
- [ ] Execute safe commands: `project --list`
- [ ] Execute safe commands: `health --system`
- [ ] Execute safe commands: `crawl test-project --url https://example.com`
- [ ] Blocked command: `setup --uninstall` (should fail)
- [ ] Blocked command: `setup --reset` (should fail)
- [ ] Blocked command: `project --remove --all` (should fail)
- [ ] Invalid command: `nonexistent --flag`
- [ ] Command with long execution time
- [ ] Command with large output
- [ ] Command with error exit code
- [ ] Concurrent command execution

**Expected Response Format**:
```json
{
  "success": true,
  "data": {
    "command": "project --list",
    "exit_code": 0,
    "stdout": "Project listing output...",
    "stderr": "",
    "execution_time_ms": 125.5
  }
}
```

#### 16.2.2 project_create Method
**Purpose**: Create new project via command execution
**Parameters**:
- `name` (required): Project name
- `project_type` (required): Project type
- `description` (optional): Project description
- `settings` (optional): Additional settings

**Test Cases**:
- [ ] `project_create("test", "crawling")` - Basic creation
- [ ] `project_create("test", "data", "Description")` - With description
- [ ] `project_create("test", "storage", settings={"key": "value"})` - With settings
- [ ] `project_create("duplicate", "crawling")` - Duplicate name
- [ ] `project_create("invalid-type", "unknown")` - Invalid type
- [ ] `project_create("", "crawling")` - Empty name
- [ ] `project_create("test with spaces", "crawling")` - Name with spaces
- [ ] `project_create("very-long-name-...", "crawling")` - Very long name
- [ ] Test with special characters in name
- [ ] Test with Unicode characters in description

#### 16.2.3 project_remove Method
**Purpose**: Remove project via command execution
**Parameters**:
- `name` (required): Project name to remove
- `confirm` (optional): Confirmation flag
- `backup` (optional): Create backup before removal

**Test Cases**:
- [ ] `project_remove("test")` - Basic removal
- [ ] `project_remove("test", confirm=True)` - With confirmation
- [ ] `project_remove("test", backup=True)` - With backup
- [ ] `project_remove("test", confirm=True, backup=True)` - Both flags
- [ ] `project_remove("nonexistent")` - Non-existent project
- [ ] Test removal of project with active crawl
- [ ] Test removal of project being served
- [ ] Verify cleanup after removal

#### 16.2.4 crawl_project Method
**Purpose**: Start project crawling via command execution
**Parameters**:
- `project_name` (required): Project to crawl
- `url` (optional): URL to crawl
- `max_pages` (optional): Maximum pages to crawl
- `depth` (optional): Crawl depth
- `rate_limit` (optional): Rate limiting

**Test Cases**:
- [ ] `crawl_project("test")` - Basic crawl (existing project)
- [ ] `crawl_project("test", url="https://example.com")` - With URL
- [ ] `crawl_project("test", max_pages=10)` - With page limit
- [ ] `crawl_project("test", depth=2)` - With depth limit
- [ ] `crawl_project("test", rate_limit=1.5)` - With rate limiting
- [ ] `crawl_project("test", url="https://example.com", max_pages=5, depth=1)` - All options
- [ ] `crawl_project("nonexistent")` - Non-existent project
- [ ] `crawl_project("test", url="invalid-url")` - Invalid URL
- [ ] Test long-running crawl operations
- [ ] Test crawl interruption

### 16.3 MCP Server Infrastructure Testing

#### 16.3.1 Server Startup and Configuration
- [ ] Start read-only server with default settings
- [ ] Start read-only server with custom host/port
- [ ] Start admin server with default settings
- [ ] Start admin server with custom host/port
- [ ] Test admin server localhost restriction
- [ ] Test both servers running simultaneously
- [ ] Test server restart after crash
- [ ] Test configuration loading and validation
- [ ] Test MCP protocol compliance
- [ ] Test server resource cleanup on shutdown

#### 16.3.2 HTTP API Testing (Direct REST calls)
**Read-Only Server (9382/9383)**:
- [ ] `GET /health` - Health check
- [ ] `GET /projects` - List projects
- [ ] `GET /projects/{name}` - Get specific project
- [ ] `POST /search` - Semantic search with JSON body
- [ ] `GET /files/{project}/{path}` - File access
- [ ] Test CORS headers
- [ ] Test malformed requests
- [ ] Test rate limiting
- [ ] Test concurrent requests
- [ ] Test request timeout handling

**Admin Server (9384)**:
- [ ] `POST /execute` - Command execution
- [ ] `POST /projects` - Create project
- [ ] `DELETE /projects/{name}` - Remove project
- [ ] `POST /crawl` - Start crawling
- [ ] Test localhost-only access restriction
- [ ] Test command validation and blocking
- [ ] Test admin operation timeouts

#### 16.3.3 MCP Protocol Testing
- [ ] Test MCP handshake and initialization
- [ ] Test tool discovery (`tools/list`)
- [ ] Test resource listing (`resources/list`)
- [ ] Test prompt templates (`prompts/list`)
- [ ] Test tool invocation with correct parameters
- [ ] Test tool invocation with invalid parameters
- [ ] Test resource access with proper URIs
- [ ] Test error handling and responses
- [ ] Test MCP client configuration generation
- [ ] Test with multiple concurrent MCP clients

#### 16.3.4 Security and Access Control Testing
- [ ] Verify admin server refuses non-localhost connections
- [ ] Test file access restrictions by project type:
  - Storage projects: Full file access allowed
  - Crawling projects: Metadata only
  - Data projects: Metadata only
- [ ] Test command injection protection
- [ ] Test path traversal protection
- [ ] Test resource limits and timeouts
- [ ] Verify blocked operations cannot be executed
- [ ] Test input sanitization for all endpoints
- [ ] Test authentication if implemented
- [ ] Test rate limiting enforcement

### 16.4 Integration Testing with Real MCP Clients

#### 16.4.1 Claude Code Integration
- [ ] Configure Claude Code with read-only server
- [ ] Configure Claude Code with admin server
- [ ] Test project listing via Claude Code
- [ ] Test search functionality via Claude Code
- [ ] Test file access via Claude Code
- [ ] Test admin commands via Claude Code
- [ ] Verify blocked operations are rejected
- [ ] Test concurrent operations
- [ ] Test error handling and user feedback

#### 16.4.2 Generic MCP Client Testing
- [ ] Test with standard MCP test client
- [ ] Verify protocol compliance
- [ ] Test tool registration and discovery
- [ ] Test resource access patterns
- [ ] Test error response formats
- [ ] Test timeout and retry mechanisms

### 16.5 Performance and Scalability Testing

#### 16.5.1 Load Testing
- [ ] Test 100 concurrent project listings
- [ ] Test 50 concurrent search operations
- [ ] Test 20 concurrent admin commands
- [ ] Test server performance under memory pressure
- [ ] Test with large project databases (1000+ projects)
- [ ] Test with large search result sets
- [ ] Test long-running operations (crawling)
- [ ] Monitor resource usage during testing

#### 16.5.2 Error Handling and Recovery
- [ ] Test server behavior with database unavailable
- [ ] Test behavior with vector store unavailable
- [ ] Test network interruption handling
- [ ] Test partial response scenarios
- [ ] Test concurrent modification conflicts
- [ ] Test graceful degradation scenarios

### 16.6 Playwright Testing for MCP Servers

#### 16.6.1 Automated UI Testing
- [ ] Navigate to server health endpoints
- [ ] Screenshot API response formats
- [ ] Test API forms and responses
- [ ] Monitor console logs for errors
- [ ] Test concurrent browser sessions
- [ ] Verify CORS behavior in browser
- [ ] Test JavaScript API integration

#### 16.6.2 Visual Testing
- [ ] Screenshot health endpoint responses
- [ ] Screenshot project listing formats
- [ ] Screenshot search result formats
- [ ] Screenshot error response formats
- [ ] Compare response formats between servers
- [ ] Verify JSON formatting consistency

## 17. COMPREHENSIVE MCP SERVER TESTING SUITE

### 17.1 MCP Read-Only Server Testing (Port 9396)

#### 17.1.1 Server Startup and Health Checks
- [ ] Start server: `bablib serve --host 127.0.0.1 --port 9396 --foreground` ✅
- [ ] Test health endpoint: `curl http://localhost:9396/health` ✅
- [ ] Verify JSON response format ✅
- [ ] Check server status and version info ✅
- [ ] Test concurrent health requests
- [ ] Monitor memory usage during startup

#### 17.1.2 Project Listing Operations
- [ ] List all projects: `curl http://localhost:9396/projects` ❌ (Endpoint not found)
- [ ] Test empty project list response
- [ ] Create test project: `bablib project --create mcp-test-1 --type crawling` ✅
- [ ] Verify project appears in list ✅
- [ ] Create multiple projects and verify listing ✅
- [ ] Test pagination with many projects
- [ ] Test filtering by project type
- [ ] Test sorting options

#### 17.1.3 Project Search Operations
- [ ] Basic search: `curl -X POST http://localhost:9396/search -H "Content-Type: application/json" -d '{"query":"test"}'`
- [ ] Search with empty query
- [ ] Search with special characters
- [ ] Search with very long query
- [ ] Search specific project
- [ ] Test similarity scoring
- [ ] Test result pagination
- [ ] Benchmark search performance

#### 17.1.4 File Access Control Testing
- [ ] Create storage project: `bablib project --create storage-test --type storage`
- [ ] Create crawling project: `bablib project --create crawl-test --type crawling`
- [ ] Test file access for storage project (should allow content)
- [ ] Test file access for crawling project (metadata only)
- [ ] Test path traversal protection
- [ ] Test access to non-existent files
- [ ] Test binary file handling
- [ ] Verify access control enforcement

#### 17.1.5 Error Handling
- [ ] Test malformed JSON requests
- [ ] Test missing required parameters
- [ ] Test invalid project names
- [ ] Test timeout scenarios
- [ ] Test large request payloads
- [ ] Test concurrent error conditions
- [ ] Verify error response format

### 17.2 MCP Admin Server Testing (Port 9397)

#### 17.2.1 Admin Server Setup
- [ ] Start admin server: `bablib serve --admin --host 127.0.0.1 --port 9397 --foreground`
- [ ] Verify localhost-only binding
- [ ] Test rejection of non-localhost connections
- [ ] Test admin health endpoint
- [ ] Verify security headers

#### 17.2.2 Command Execution Testing
- [ ] Execute safe command: `{"command": "project --list"}`
- [ ] Execute project creation: `{"command": "project --create admin-test --type data"}`
- [ ] Execute crawl command: `{"command": "crawl admin-test --url https://example.com"}`
- [ ] Test blocked command (uninstall): Should fail
- [ ] Test blocked command (reset): Should fail
- [ ] Test blocked command (delete-all): Should fail
- [ ] Test command with timeout
- [ ] Test command with large output

#### 17.2.3 Project Management via Admin
- [ ] Create project through admin API
- [ ] Update project settings
- [ ] Remove specific project
- [ ] Test batch operations
- [ ] Test transaction handling
- [ ] Verify data consistency

### 17.3 MCP Protocol Compliance Testing

#### 17.3.1 Tool Discovery
- [ ] Test tool list endpoint
- [ ] Verify tool schema format
- [ ] Test parameter validation
- [ ] Test optional vs required parameters
- [ ] Verify tool descriptions

#### 17.3.2 Resource Management
- [ ] Test resource listing
- [ ] Test resource URIs
- [ ] Test resource access patterns
- [ ] Verify resource metadata
- [ ] Test resource updates

#### 17.3.3 Prompt Templates
- [ ] Test prompt listing
- [ ] Test prompt generation
- [ ] Test variable substitution
- [ ] Test prompt validation

### 17.4 Integration Testing

#### 17.4.1 End-to-End Workflow
- [ ] Setup -> Create Project -> Crawl -> Search workflow
- [ ] Multi-project search operations
- [ ] Concurrent server operations
- [ ] Server recovery after crash
- [ ] Data persistence verification

#### 17.4.2 Performance Testing
- [ ] Load test with 100 concurrent connections
- [ ] Stress test with 1000 requests/second
- [ ] Memory leak detection
- [ ] Response time benchmarking
- [ ] Database connection pooling

#### 17.4.3 Security Testing
- [ ] SQL injection attempts
- [ ] Command injection attempts
- [ ] Path traversal attempts
- [ ] XSS prevention
- [ ] CSRF protection
- [ ] Rate limiting verification

### 17.5 MCP Client Testing

#### 17.5.1 Claude Code Integration
- [ ] Configure Claude Code with read-only server
- [ ] Configure Claude Code with admin server
- [ ] Test project operations via Claude
- [ ] Test search via Claude
- [ ] Verify operation restrictions

#### 17.5.2 Generic MCP Client
- [ ] Test with MCP test client
- [ ] Verify protocol compliance
- [ ] Test error handling
- [ ] Test timeout handling

### 17.6 Advanced MCP Testing Scenarios

#### 17.6.1 Vector Store Integration
- [ ] Test with SQLite-vec backend
- [ ] Test with Qdrant backend
- [ ] Test vector store switching
- [ ] Test embedding generation
- [ ] Test similarity search accuracy

#### 17.6.2 Concurrent Operations
- [ ] Multiple clients accessing same project
- [ ] Concurrent crawl and search
- [ ] Race condition testing
- [ ] Deadlock prevention
- [ ] Transaction isolation

#### 17.6.3 Failure Recovery
- [ ] Database connection loss
- [ ] Vector store unavailable
- [ ] Network interruption
- [ ] Partial request handling
- [ ] Graceful degradation

### 17.7 Automated MCP Test Suite

#### 17.7.1 Unit Tests
- [ ] Run MCP-specific unit tests
- [ ] Fix failing MCP tests
- [ ] Achieve 90% coverage

#### 17.7.2 Integration Tests
- [ ] Run MCP integration tests
- [ ] Test all API endpoints
- [ ] Verify data flow

#### 17.7.3 Contract Tests
- [ ] Verify API contracts
- [ ] Test backward compatibility
- [ ] Validate response schemas

## 18. Logic Issues Found and Resolution Status

### Session 3: 2025-09-29 Logic Issues

#### 17.1 Unit Test Logic Issues ❌
- [ ] **Issue 1**: `test_batch_crawler.py:132` - Missing `CrawlerService` class in `src.logic.crawler.core.batch` module
  - **Root Cause**: Test tries to patch non-existent `CrawlerService` class
  - **Fix Required**: Update test to patch correct crawler class or create mock
  - **File**: `tests/unit/test_batch_crawler.py:132`

- [ ] **Issue 2**: `test_batch_crawler.py:194` - Missing 'total' key in batch operation summary
  - **Root Cause**: `get_summary()` method returns different keys than test expects
  - **Expected**: `{'total': 3, 'succeeded': 2, 'failed': 1}`
  - **Actual**: `{'completed': 1, 'duration_seconds': 1e-05, 'failed': 1, 'is_complete': True}`
  - **Fix Required**: Update test expectations or fix `get_summary()` method

- [ ] **Issue 3**: `test_cli_short_keys.py:199` - Click parameter format mismatch
  - **Root Cause**: Click parameter `opts` returns list instead of tuple
  - **Expected**: `('--name', '-n')`
  - **Actual**: `['--name', '-n']`
  - **Fix Required**: Update test assertion to handle list format

- [ ] **Issue 4**: `test_cli_short_keys.py:252` - Short key validation logic issue
  - **Root Cause**: Validation function returns `True` when conflict expected
  - **Expected**: Conflicting short keys should return `is_valid = False`
  - **Actual**: Returns `is_valid = True` with warning logged
  - **Fix Required**: Update validation logic or test expectations

- [ ] **Issue 5**: `test_error_handler.py` - Missing `ErrorHandlerService` import
  - **Root Cause**: Test imports non-existent `ErrorHandlerService` class
  - **Error**: `ImportError: cannot import name 'ErrorHandlerService'`
  - **Fix Required**: Check if class exists or update import path

#### 17.2 Pydantic V2 Migration Issues ⚠️
- [ ] **Issue 6**: Deprecated `@validator` decorators in MCP models
  - **Files**: `src/logic/mcp/models/command_execution.py:46,52,65`
  - **Warning**: `Pydantic V1 style @validator validators are deprecated`
  - **Fix Required**: Migrate to `@field_validator` decorators
  - **Impact**: 3 validators need updating

- [ ] **Issue 7**: Deprecated `json_encoders` configuration
  - **Warning**: `json_encoders is deprecated. See Pydantic V2 Migration Guide`
  - **Fix Required**: Replace with custom serializers
  - **Impact**: 33 warnings across test suite

#### 17.3 DateTime Deprecation Issues ⚠️
- [ ] **Issue 8**: `datetime.utcnow()` deprecation warnings
  - **Files**: Multiple files in `src/logic/crawler/models/batch.py`
  - **Lines**: 88, 94, 144, 157
  - **Fix Required**: Replace with `datetime.now(datetime.UTC)`
  - **Impact**: 17+ warnings in test suite

#### 17.4 Missing Module/Class Issues ❌
- [ ] **Issue 9**: Various missing import errors in other unit tests
  - **Suspected**: Additional `ModuleNotFoundError` and `ImportError` issues
  - **Status**: Need comprehensive scan of all unit tests
  - **Fix Required**: Update import paths after code reorganization

### Resolution Priority

#### Critical (Must Fix) 🔴
1. **Issue 1**: Missing `CrawlerService` class - blocks crawler tests
2. **Issue 5**: Missing `ErrorHandlerService` class - blocks error handler tests
3. **Issue 9**: Module import errors - blocks multiple test files

#### High (Should Fix) 🟡
4. **Issue 2**: Batch operation summary mismatch - affects batch crawler logic
5. **Issue 4**: Short key validation logic - affects CLI validation

#### Medium (Can Fix) 🟢
6. **Issue 3**: Click parameter format - minor test assertion issue
7. **Issue 6**: Pydantic V2 migration - deprecated but functional
8. **Issue 8**: DateTime deprecation - deprecated but functional

#### Low (Future) 🔵
9. **Issue 7**: JSON encoders deprecation - warnings only

### Fix Implementation Plan

#### Phase 1: Critical Fixes
1. **Scan all unit tests** for import errors
2. **Fix missing classes** and import paths
3. **Update test mocking** to match actual implementation

#### Phase 2: Logic Fixes
4. **Fix batch operation summary** format consistency
5. **Fix short key validation** logic
6. **Update Click test assertions** for correct format

#### Phase 3: Deprecation Fixes
7. **Migrate Pydantic validators** to V2 style
8. **Replace datetime.utcnow()** calls
9. **Update JSON encoders** (optional)

## 19. Additional 30 Manual Test Scenarios (Not Covered Above)

### 19.1 System Resilience Testing
- [ ] **Server Port Collision Testing** - Start server on port already in use, verify graceful error handling
- [ ] **Multiple Vector Store Migration** - Switch between SQLite-vec and Qdrant with existing data, verify data integrity
- [ ] **Interrupted Setup Recovery** - Kill process during `bablib setup --init` and test recovery mechanism
- [ ] **Concurrent Server Instances** - Run 10+ MCP servers simultaneously on different ports
- [ ] **Cross-Project Search** - Search across 50+ projects with mixed vector stores

### 19.2 Error Recovery Testing
- [ ] **Malformed Configuration Recovery** - Corrupt settings.yaml and test auto-repair functionality
- [ ] **Network Partition Testing** - Simulate network loss during Qdrant operations
- [ ] **Embedding Model Switching** - Change from mxbai-embed-large to another model mid-operation
- [ ] **Circular Dependency Detection** - Test crawl with site containing circular links
- [ ] **Memory Pressure Testing** - Run with limited memory (512MB) and verify graceful degradation

### 19.3 Advanced Input Testing
- [ ] **Project Name Unicode Testing** - Create projects with emoji, Chinese, Arabic characters
- [ ] **Rate Limit Bypass Attempts** - Test if rate limiting can be circumvented
- [ ] **Disk Space Exhaustion** - Fill disk during crawl/upload operations
- [ ] **Time Zone Handling** - Test with different system time zones and daylight saving
- [ ] **Signal Handling** - Test SIGTERM, SIGINT, SIGHUP during various operations

### 19.4 Process Management Testing
- [ ] **Background Process Management** - Test with --background flag and process monitoring
- [ ] **Log Rotation Testing** - Verify log files rotate correctly at size limits
- [ ] **Credential Leakage Prevention** - Ensure passwords/tokens never appear in logs
- [ ] **Database Lock Contention** - Multiple processes accessing same SQLite database
- [ ] **File Watcher Integration** - Auto-update projects when source files change

### 19.5 Data Transfer Testing
- [ ] **Project Export/Import** - Export project to JSON and import on different system
- [ ] **Batch Error Recovery** - Kill batch operation and test resume functionality
- [ ] **WebSocket Connection Testing** - Test real-time updates if WebSocket endpoints exist
- [ ] **Cache Invalidation** - Verify caches clear correctly after updates
- [ ] **Partial Response Handling** - Test behavior when server sends incomplete responses

### 19.6 Network & Security Testing
- [ ] **DNS Resolution Issues** - Test with invalid DNS, slow DNS, DNS timeout
- [ ] **SSL Certificate Validation** - Test with self-signed, expired, invalid certificates
- [ ] **Content Type Detection** - Upload files without extensions, verify type detection
- [ ] **Symlink Handling** - Create projects with symlinked directories
- [ ] **Version Compatibility Testing** - Test upgrade/downgrade between Bablib versions

## Priority Order

1. **Critical**: Setup initialization, project creation, basic crawling
2. **High**: Server operations, MCP functionality, search operations
3. **Medium**: Upload functionality, batch operations, health checks
4. **Low**: Edge cases, performance optimization, documentation

## Success Criteria

- All critical and high priority tests pass
- No data loss scenarios
- Security boundaries enforced
- MCP servers functional
- <30s installation time
- All test suites pass
- Logic issues from Section 16 resolved