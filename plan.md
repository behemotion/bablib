# Box-Centric Architecture Refactoring Plan

**Date**: 2025-11-29
**Goal**: Refactor all data operations to work with Boxes instead of Projects

---

## Architecture Overview

### Current State (Wrong)
```
Project → contains pages, crawl sessions, uploaded files
Shelf → groups Projects
```

### Target State (Correct)
```
Box → contains pages, crawl sessions, uploaded files (primary data container)
Shelf → groups Boxes for access control only (no data storage)
```

---

## Phase 1: Database Schema Migration

### Task 1.1: Add box_id to crawl tables
- [x] Create migration script for schema v5
- [x] Add `box_id TEXT` column to `pages` table
- [x] Add `box_id TEXT` column to `crawl_sessions` table
- [x] Create indexes: `idx_pages_box_id`, `idx_crawl_sessions_box_id`
- [x] Added `_get_box_db_path()` and `_get_box_connection()` methods

**File**: `src/services/database.py`
**Lines**: ~228-340 (box connection methods)

### Task 1.2: Create data migration
- [x] Schema uses `box_id` for new box-specific databases
- [ ] Data migration for existing projects (if needed)

**File**: `src/services/database_migrator.py`

---

## Phase 2: Model Updates

### Task 2.1: Update CrawlSession model
- [x] Renamed `project_id` field to `box_id`
- [x] Updated field description
- [x] Updated `to_dict()` method

**File**: `src/logic/crawler/models/session.py`

### Task 2.2: Update Page model
- [x] Renamed `project_id` field to `box_id`
- [x] Updated field description
- [x] Updated `to_dict()` method

**File**: `src/logic/crawler/models/page.py`

### Task 2.3: Update src/models/page.py
- [x] Confirmed duplicate model exists
- [x] Applied same `box_id` changes

**File**: `src/models/page.py`

### Task 2.4: Update additional models
- [x] Updated `UploadOperation` model (`project_id` → `box_id`)
- [x] Updated `StorageFile` model (`project_id` → `box_id`)
- [x] Updated `DataDocument` model (`project_id` → `box_id`)
- [x] Updated `QueryResult` model (`project_id` → `box_id`)

**Files**: `src/logic/projects/models/upload.py`, `src/logic/projects/models/files.py`, `src/models/query_result.py`

---

## Phase 3: Crawler Service Refactoring

### Task 3.1: Update DocumentationCrawler.start_crawl()
- [x] Changed parameter `project_id: str` to `box_id: str`
- [x] Updated method to fetch Box instead of Project
- [x] Get crawl settings (`box.url`, `box.crawl_depth`) from Box
- [x] Updated all internal references

**File**: `src/logic/crawler/core/crawler.py`
**Method**: `start_crawl()`

### Task 3.2: Update DocumentationCrawler.resume_crawl()
- [x] Changed to use `box_id` instead of `project_id`
- [x] Updated database queries to use `get_box_pages()`

**File**: `src/logic/crawler/core/crawler.py`
**Method**: `resume_crawl()`

### Task 3.3: Update DocumentationCrawler._crawl_worker()
- [x] Updated all `project` references to `box`
- [x] Updated page creation calls to use `box_id`
- [x] Added `max_depth` local variable from `box.crawl_depth`

**File**: `src/logic/crawler/core/crawler.py`
**Method**: `_crawl_worker()`

### Task 3.4: Update DocumentationCrawler.retry_crawl()
- [x] Changed parameter to `box_id`

**File**: `src/logic/crawler/core/crawler.py`
**Method**: `retry_crawl()`

### Task 3.5: Update BatchCrawler
- [x] Updated `start_crawl()` call to use `box_id`
- [x] Added `get_box_by_name()` / `create_box()` calls
- [ ] Full migration of BatchCrawler (TODO noted)

**File**: `src/logic/crawler/core/batch.py`

---

## Phase 4: Database Manager Updates

### Task 4.1: Update create_crawl_session()
- [x] Changed parameter from `project_id` to `box_id`
- [x] Updated to use `_get_box_connection()`
- [x] Updated SQL INSERT to use `box_id`

**File**: `src/services/database.py`

### Task 4.2: Update create_page()
- [x] Changed parameter from `project_id` to `box_id`
- [x] Updated to use `_get_box_connection()`
- [x] Updated SQL INSERT to use `box_id`

**File**: `src/services/database.py`

### Task 4.3: Add get_box_pages()
- [x] Added new `get_box_pages()` method
- [x] Kept `get_project_pages()` for backward compatibility

**File**: `src/services/database.py`

### Task 4.4: Update other methods
- [x] Updated `get_page_by_url()` to use `box_id`
- [x] Updated `update_page()` to use `box_id`
- [x] Updated `update_crawl_session()` to use `box_id`
- [x] Updated `_page_from_row()` to use `box_id`
- [x] Updated `_session_from_row()` to use `box_id`
- [x] Added `get_box_by_name()` helper method

**File**: `src/services/database.py`

---

## Phase 5: Upload Manager Refactoring

### Task 5.1: Update UploadManager.upload_files()
- [x] Change parameter from `project: Project` to `box: Box`
- [x] Update all internal references
- [x] Update UploadOperation creation to use `box_id`

**File**: `src/logic/projects/upload/upload_manager.py`
**Method**: `upload_files()` (line ~62)

### Task 5.2: Update UploadOperation model
- [x] Change `project_id` to `box_id` (already done in Phase 2)

**File**: `src/logic/projects/models/upload.py`

### Task 5.3: Update validation and processing methods
- [x] Updated `validate_upload()` to use Box and BoxType
- [x] Updated `_execute_upload()` to use box
- [x] Updated `_process_single_file()` to use box
- [x] Renamed `_process_file_for_project_type()` to `_process_file_for_box_type()`
- [x] Renamed `_store_file_in_storage_project()` to `_store_file_in_bag_box()`
- [x] Renamed `_process_file_for_data_project()` to `_process_file_for_rag_box()`
- [x] Added `get_box_data_path()` to `src/lib/paths.py`

**Files**: `src/logic/projects/upload/upload_manager.py`, `src/lib/paths.py`

---

## Phase 6: Storage Service Refactoring (LOW PRIORITY)

**Note**: FillService now uses UploadManager for both RAG and BAG boxes, which already uses `box_id`.
The `StorageProject` class is legacy code that can be refactored later.

### Task 6.1: Rename StorageProject → BoxStorage (DEFERRED)
- [ ] Rename class (optional - UploadManager handles BAG boxes)
- [ ] Update all method signatures to accept Box
- [ ] Update internal references

**File**: `src/logic/projects/types/storage_project.py` → `src/logic/box/storage.py`

### Task 6.2: Update DataProject if needed (DEFERRED)
- [ ] Review for project_id references
- [ ] Update to box_id if applicable

**File**: `src/logic/projects/types/data_project.py`

---

## Phase 7: FillService Integration

### Task 7.1: Wire up _fill_drag() to DocumentationCrawler
- [x] Imported DocumentationCrawler
- [x] Create DatabaseManager instance with BablibConfig
- [x] Call `crawler.start_crawl(box_id=box.id, ...)`
- [x] Wait for completion with `crawler.wait_for_completion()`
- [x] Return actual crawl results with session stats

**File**: `src/services/fill_service.py`
**Method**: `_fill_drag()`

### Task 7.2: Wire up _fill_rag() to UploadManager
- [x] Import UploadManager
- [x] Create UploadSource from source string via `UploadSource.parse()`
- [x] Call `upload_manager.upload_files(box=box, ...)`
- [x] Wait for completion and return actual upload results

**File**: `src/services/fill_service.py`
**Method**: `_fill_rag()`

### Task 7.3: Wire up _fill_bag() to UploadManager
- [x] Import UploadManager (BAG boxes use same UploadManager as RAG)
- [x] Create UploadSource from source string via `UploadSource.parse()`
- [x] Call `upload_manager.upload_files(box=box, ...)` with BAG-specific options
- [x] Wait for completion and return actual storage results

**File**: `src/services/fill_service.py`
**Method**: `_fill_bag()`

---

## Phase 8: MCP Endpoint Updates

### Task 8.1: Update MCP read-only endpoints
- [x] Ensure box listing respects shelf membership (via ShelfMcpService)
- [x] Updated shelf_mcp_service.py to use box-centric methods

**File**: `src/logic/mcp/services/read_only.py` (uses ProjectManager - higher level abstraction)

### Task 8.2: Update MCP shelf service
- [x] Updated `_get_box_file_count()` to use `get_box_pages()` instead of `get_project_pages()`
- [x] Updated `_get_box_total_size()` to use box-centric approach
- [x] Updated `_get_box_file_list()` to use box-centric approach

**File**: `src/logic/mcp/services/shelf_mcp_service.py`

---

## Phase 9: Test Updates

### Task 9.1: Update crawler tests
- [ ] Change all `project_id` fixtures to `box_id`
- [ ] Update assertions

**Files**: `tests/unit/test_crawler*.py`, `tests/integration/test_crawl*.py`

### Task 9.2: Update upload tests
- [ ] Change Project mocks to Box mocks
- [ ] Update assertions

**Files**: `tests/*/test_upload*.py`

### Task 9.3: Update database tests
- [ ] Update schema tests for new columns
- [ ] Add migration tests

**Files**: `tests/unit/test_database*.py`

### Task 9.4: Run full test suite
- [ ] `uv run pytest tests/unit/ -v`
- [ ] `uv run pytest tests/integration/ -v`
- [ ] `uv run pytest tests/contract/ -v`
- [ ] Fix any failures

---

## Phase 10: Cleanup

### Task 10.1: Remove deprecated project_id columns
- [ ] Create final migration to drop project_id from pages table
- [ ] Create final migration to drop project_id from crawl_sessions table
- [ ] Only after confirming all code uses box_id

### Task 10.2: Update documentation
- [ ] Update CLAUDE.md with new architecture
- [ ] Update any API documentation

### Task 10.3: Remove backward compatibility code
- [ ] Remove any temporary dual-column logic
- [ ] Clean up migration scripts

---

## File Impact Summary

| File | Change Type | Priority |
|------|-------------|----------|
| `src/services/database.py` | Schema + Methods | HIGH |
| `src/logic/crawler/core/crawler.py` | Major refactor | HIGH |
| `src/logic/crawler/models/session.py` | Field rename | HIGH |
| `src/logic/crawler/models/page.py` | Field rename | HIGH |
| `src/logic/crawler/core/batch.py` | Refactor | MEDIUM |
| `src/logic/projects/upload/upload_manager.py` | Refactor | MEDIUM |
| `src/logic/projects/models/upload.py` | Field rename | MEDIUM |
| `src/services/fill_service.py` | Wire up | MEDIUM |
| `src/logic/projects/types/storage_project.py` | Rename + Refactor | MEDIUM |
| `src/logic/mcp/services/*.py` | Updates | LOW |
| `tests/**/*.py` | Test updates | LOW |

---

## Estimated Effort

- **Phase 1-2** (Schema + Models): ~2 hours
- **Phase 3-4** (Crawler + DB): ~4 hours
- **Phase 5-6** (Upload + Storage): ~2 hours
- **Phase 7** (FillService): ~1 hour
- **Phase 8** (MCP): ~1 hour
- **Phase 9-10** (Tests + Cleanup): ~2 hours

**Total**: ~12 hours

---

## Success Criteria

1. [ ] All `bablib fill <box>` commands work for drag/rag/bag types
2. [ ] Crawled pages stored with `box_id` in database
3. [ ] Uploaded files associated with `box_id`
4. [ ] MCP endpoints filter boxes by shelf membership
5. [ ] All tests passing
6. [ ] No references to `project_id` in crawler/upload code paths
