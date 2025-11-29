# Context-Aware Commands Validation Checklist

**Based on**: specs/019-spicing-commands-up/quickstart.md
**Date**: 2025-09-29
**Status**: Ready for manual validation

## Overview

This checklist covers manual validation scenarios for context-aware command enhancement features. Each scenario should be tested to ensure proper functionality before release.

## Prerequisites

```bash
# Ensure Bablib is installed
uv tool install . --force --reinstall

# Verify installation
bablib --version

# Check system health
bablib health --system --services
```

## Scenario 1: New User Setting Up Documentation

**Goal**: Create and configure a shelf for project documentation

### Test Steps

- [ ] **Step 1.1**: Access non-existent shelf
  ```bash
  bablib shelf project-docs
  ```
  - **Expected**: Prompt "Shelf 'project-docs' not found. Create it? (y/n)"
  - **Action**: Enter `y`
  - **Expected**: Shelf created, prompt "Launch setup wizard? (y/n)"
  - **Action**: Enter `y`

- [ ] **Step 1.2**: Complete shelf wizard
  - **Step 1/5 - Description**
    - Prompt: "Enter description (optional):"
    - Enter: "Main project documentation"
  - **Step 2/5 - Auto-fill**
    - Prompt: "Auto-fill empty boxes when accessed? (y/n)"
    - Enter: `y`
  - **Step 3/5 - Default box type**
    - Prompt: "Default box type: (1) drag (2) rag (3) bag"
    - Enter: `1`
  - **Step 4/5 - Tags**
    - Prompt: "Add tags (comma-separated, optional):"
    - Enter: "docs,main,project"
  - **Step 5/5 - Confirmation**
    - Shows summary of collected data
    - Enter: `y` to confirm

- [ ] **Step 1.3**: Verify shelf configuration
  ```bash
  bablib shelf project-docs
  ```
  - **Expected**: Shows configured shelf status
  - **Expected**: Shows "Shelf is empty. Would you like to create some boxes?"

### Success Criteria
- ✓ No manual configuration file editing required
- ✓ Clear prompts at each step
- ✓ Shelf properly configured and ready for use
- ✓ Wizard collected and applied all configuration

## Scenario 2: Filling Content Based on Box Type

**Goal**: Create different box types and fill them appropriately

### Test Steps

- [ ] **Step 2.1**: Create drag box with wizard
  ```bash
  bablib box website-docs --type drag --init
  ```
  - **Expected**: Box created, wizard launches
  - **Step 1**: Type confirmation (drag - Website crawler)
  - **Step 2**: Description input
  - **Step 3**: Auto-process setting
  - **Step 4**: Crawler preferences (max-pages, rate-limit, depth)
  - **Step 5**: Initial URL prompt
  - **Expected**: "Box ready! Provide website URL to start crawling."

- [ ] **Step 2.2**: Create rag box with wizard
  ```bash
  bablib box local-files --type rag --init
  ```
  - **Expected**: Box created, wizard launches
  - **Wizard collects**: File patterns, chunk size preferences
  - **Expected**: "Box ready! Provide file path to upload documents."

- [ ] **Step 2.3**: Create bag box with wizard
  ```bash
  bablib box data-store --type bag --init
  ```
  - **Expected**: Box created, wizard launches
  - **Wizard collects**: Storage preferences, file type filters
  - **Expected**: "Box ready! Provide content path to store files."

- [ ] **Step 2.4**: Access each empty box
  ```bash
  bablib box website-docs
  ```
  - **Expected**: Type-specific prompt for website URL

  ```bash
  bablib box local-files
  ```
  - **Expected**: Type-specific prompt for file path

  ```bash
  bablib box data-store
  ```
  - **Expected**: Type-specific prompt for content path

### Success Criteria
- ✓ Type-specific prompts and suggestions provided
- ✓ Appropriate fill workflows launched
- ✓ Content successfully processed according to type

## Scenario 3: MCP Server Setup with Wizard

**Goal**: Configure MCP server for AI assistant integration

### Test Steps

- [ ] **Step 3.1**: Launch MCP setup wizard
  ```bash
  bablib serve --init
  ```
  - **Expected**: MCP setup wizard launches
  - **Step 1**: "Enable read-only server? (y/n)"
    - Enter: `y`
  - **Step 2**: "Read-only server port [9383]:"
    - Enter: Press Enter (accept default)
  - **Step 3**: "Enable admin server? (y/n)"
    - Enter: `y`
  - **Step 4**: "Admin server port [9384]:"
    - Enter: Press Enter (accept default)
  - **Step 5**: "Auto-start with system? (y/n)"
    - Enter: `n`
  - **Step 6**: Confirmation summary
    - Enter: `y` to confirm

- [ ] **Step 3.2**: Start configured servers
  ```bash
  bablib serve
  ```
  - **Expected**: Both servers start with configured settings
  - **Expected**: Connection info displayed for AI assistant setup

- [ ] **Step 3.3**: Test read-only server
  ```bash
  curl http://localhost:9383/health
  ```
  - **Expected**: Health check response

- [ ] **Step 3.4**: Test admin server
  ```bash
  curl http://127.0.0.1:9384/health
  ```
  - **Expected**: Health check response

### Success Criteria
- ✓ MCP servers configured without manual file editing
- ✓ Clear connection instructions provided
- ✓ Both read-only and admin servers functional

## Scenario 4: Flag Consistency Experience

**Goal**: Use standardized flags across all commands

### Test Steps

- [ ] **Step 4.1**: Test short flag consistency
  ```bash
  bablib shelf list -v          # --verbose
  bablib box create test -t drag -i  # --type, --init
  bablib fill web-box -s https://example.com -d 3  # --source, --depth
  bablib serve -a -h 127.0.0.1 -p 9385  # --admin, --host, --port
  ```
  - **Expected**: All commands execute with short flags
  - **Expected**: Consistent behavior across commands

- [ ] **Step 4.2**: Test help consistency
  ```bash
  bablib shelf --help
  bablib box --help
  bablib fill --help
  bablib serve --help
  ```
  - **Expected**: Standardized flag format in help output
  - **Expected**: Same flag style and descriptions
  - **Expected**: Consistent help text format

- [ ] **Step 4.3**: Test error message consistency
  ```bash
  bablib box create test --invalid-flag
  ```
  - **Expected**: "Unknown flag '--invalid-flag'. Did you mean '--init' (-i)?"

  ```bash
  bablib fill nonexistent --source test
  ```
  - **Expected**: "Box 'nonexistent' not found. Create it? (y/n)"

### Success Criteria
- ✓ All flags follow single-word pattern with single-letter shorts
- ✓ Help text uses consistent format and terminology
- ✓ Error messages provide helpful suggestions

## Performance Validation

### Command Response Times

- [ ] **Context detection (<500ms)**
  ```bash
  time bablib shelf test-shelf
  time bablib box test-box
  ```
  - **Expected**: Response time < 500ms for each

- [ ] **Wizard step transitions (<200ms)**
  - Start wizard: `bablib shelf new-shelf --init`
  - Measure time between step prompts
  - **Expected**: Each transition < 200ms

- [ ] **Status display (<1s)**
  ```bash
  time bablib shelf existing-shelf
  time bablib box existing-box
  ```
  - **Expected**: Display time < 1s for each

- [ ] **Creation operations (<2s)**
  ```bash
  time bablib shelf create perf-test
  time bablib box create perf-box --type rag
  ```
  - **Expected**: Creation time < 2s for each

### Memory Usage Validation

- [ ] **Check baseline memory**
  ```bash
  ps aux | grep bablib
  ```
  - Record baseline memory usage

- [ ] **Run multiple wizards simultaneously**
  ```bash
  for i in {1..5}; do
    bablib shelf test-shelf-$i --init &
  done
  ```
  - Monitor memory during concurrent wizards
  - **Expected**: Memory overhead < 50MB per wizard

- [ ] **Check memory after wizards complete**
  ```bash
  ps aux | grep bablib
  ```
  - Verify memory is released after completion

### Database Query Efficiency

- [ ] **Test context caching**
  ```bash
  # First call - queries database
  bablib shelf test-shelf

  # Second call - should use cache
  bablib shelf test-shelf

  # Third call - should use cache
  bablib shelf test-shelf
  ```
  - Monitor database queries (if logging enabled)
  - **Expected**: Only first call queries database

- [ ] **Test list operations**
  ```bash
  bablib shelf list --verbose
  ```
  - **Expected**: No N+1 queries (should batch load box counts)

## Vector Database Compatibility

### SQLite-vec Backend

- [ ] **Set environment**
  ```bash
  export BABLIB_VECTOR_STORE=sqlite_vec
  ```

- [ ] **Test context awareness**
  ```bash
  bablib shelf sqlite-test --init
  bablib box create sqlite-box --type drag --init
  ```
  - **Expected**: All context features work correctly
  - **Expected**: Wizard flows complete successfully

### Qdrant Backend (if available)

- [ ] **Set environment**
  ```bash
  export BABLIB_VECTOR_STORE=qdrant
  ```

- [ ] **Test context awareness**
  ```bash
  bablib shelf qdrant-test --init
  bablib box create qdrant-box --type rag --init
  ```
  - **Expected**: Identical behavior to SQLite-vec
  - **Expected**: All features work consistently

## MCP Server Integration

- [ ] **Start MCP servers**
  ```bash
  bablib serve --init
  ```

- [ ] **Test context endpoints**
  ```bash
  curl http://localhost:9383/context/shelf/test-shelf
  curl http://localhost:9383/context/box/test-box
  curl http://localhost:9383/wizards/available
  curl http://localhost:9383/flags/definitions
  ```
  - **Expected**: Valid JSON responses with context data

- [ ] **Test admin endpoints**
  ```bash
  curl -X POST http://localhost:9384/admin/context/create-shelf \
    -H "Content-Type: application/json" \
    -d '{"name": "api-test", "run_wizard": true}'
  ```
  - **Expected**: Shelf created via API

## Backward Compatibility

- [ ] **Test existing commands**
  ```bash
  bablib shelf create legacy-shelf --description "Works as before"
  bablib box create legacy-box --type rag --shelf legacy-shelf
  bablib fill legacy-box --source /path/to/docs
  ```
  - **Expected**: All commands work unchanged
  - **Expected**: No breaking changes to existing workflows

- [ ] **Test legacy flag patterns**
  ```bash
  bablib serve --host 0.0.0.0 --port 9383
  ```
  - **Expected**: Works with possible deprecation warning
  - **Suggested**: "Consider using -h and -p short forms"

## Error Recovery

- [ ] **User cancellation scenarios**
  ```bash
  bablib shelf nonexistent
  ```
  - When prompted "Create it? (y/n)", respond: `n`
  - **Expected**: Shows alternative action menu
  - **Expected**: Exits gracefully

- [ ] **Wizard interruption (Ctrl+C)**
  ```bash
  bablib box create test --init
  ```
  - Press Ctrl+C during wizard
  - **Expected**: Cleanup partial state
  - **Expected**: Offer recovery options or clean exit

- [ ] **Invalid wizard responses**
  ```bash
  bablib shelf create wizard-test --init
  ```
  - Provide invalid inputs during wizard (e.g., port 99999)
  - **Expected**: Clear error messages
  - **Expected**: Retry prompts
  - **Expected**: No wizard crash

## Validation Summary

### Checklist Completion

- [ ] Scenario 1: New User Setup (__ / __ steps passed)
- [ ] Scenario 2: Content Filling (__ / __ steps passed)
- [ ] Scenario 3: MCP Server Setup (__ / __ steps passed)
- [ ] Scenario 4: Flag Consistency (__ / __ steps passed)
- [ ] Performance Validation (__ / __ tests passed)
- [ ] Vector DB Compatibility (__ / __ tests passed)
- [ ] MCP Integration (__ / __ tests passed)
- [ ] Backward Compatibility (__ / __ tests passed)
- [ ] Error Recovery (__ / __ tests passed)

### Issues Found

| Issue # | Scenario | Description | Severity | Status |
|---------|----------|-------------|----------|--------|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

### Success Metrics Target

- **Creation Success Rate**: >95% of shelf/box creation attempts succeed
- **Wizard Completion Rate**: >85% of started wizards complete successfully
- **Error Recovery Rate**: >90% of errors result in successful user resolution
- **Performance Targets**:
  - Context Detection: <500ms average
  - Wizard Steps: <200ms average transitions
  - Memory Usage: <50MB per active wizard
  - Cache Hit Rate: >80% for repeated checks within 5 minutes

### Validation Notes

- Record any unexpected behavior or edge cases
- Note performance outliers (especially network-dependent operations)
- Document any workarounds needed
- Suggest improvements for UX or error messages

### Sign-Off

- [ ] All critical scenarios passed
- [ ] Performance requirements met
- [ ] No blocking issues found
- [ ] Ready for release

**Validated by**: _____________
**Date**: _____________
**Notes**: _____________