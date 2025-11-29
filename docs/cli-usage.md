# Bablib CLI Usage Guide

## Overview
Bablib is a powerful documentation crawler and search tool with advanced CLI capabilities. This guide covers all CLI improvements and features.

## Table of Contents
- [Getting Help](#getting-help)
- [Debug Mode](#debug-mode)
- [Creating Projects](#creating-projects)
- [Crawling Documentation](#crawling-documentation)
- [Batch Operations](#batch-operations)
- [Progress Visualization](#progress-visualization)
- [Error Reporting](#error-reporting)

## Getting Help

### Quick Help
When you run `bablib` without any arguments, you'll see a helpful suggestion:
```bash
$ bablib
Bablib CLI

No command specified. Try 'bablib --help' for available commands.

Quick start:
  bablib create                 Create a new documentation project
  bablib crawl                  Crawl documentation for a project
  bablib search                 Search indexed documentation
  bablib --help                Show all available commands
```

### Comprehensive Help
The `--help` flag shows all available commands and their options:
```bash
$ bablib --help
Usage: bablib [OPTIONS] COMMAND [ARGS]...

Bablib - Documentation crawler and search tool with RAG capabilities.

Options:
  --config-file PATH     Configuration file path
  --verbose, -v         Verbose output
  --debug               Enable debug output
  --quiet, -q           Suppress non-essential output
  --json                Output in JSON format
  --no-color            Disable colored output
  --no-progress         Disable progress indicators
  --help                Show this message and exit.

Commands:
  create    Create a new documentation project
  crawl     Crawl documentation for a project
  list      List all documentation projects
  search    Search indexed documentation
  remove    Remove a project
  serve     Start MCP server
  status    Check system status
```

### Command-Specific Help
Get detailed help for any command:
```bash
$ bablib crawl --help
Usage: bablib crawl [OPTIONS] [NAME]

Crawl documentation for a project.

Options:
  --update              Update existing project(s)
  --all                 Process all projects
  --max-pages, -m INT   Maximum pages to crawl
  --rate-limit, -r FLOAT Requests per second
  --debug               Show detailed crawl output
  --help                Show this message and exit.
```

## Debug Mode

### Enabling Debug Output
The `--debug` flag enables verbose logging for troubleshooting:
```bash
$ bablib --debug list
[2024-01-26 10:15:23] - cli - DEBUG - Bablib application initialized with debug mode
[2024-01-26 10:15:23] - cli - DEBUG - Loading projects from database
[2024-01-26 10:15:23] - cli - DEBUG - Found 3 projects
...
```

### Conditional Logging
By default, INFO level messages are hidden. They only appear with `--debug`:
- **Without debug**: Clean, minimal output
- **With debug**: Full logging including timestamps, levels, and component names

### Library Logging
Third-party library logs (urllib3, requests, etc.) are automatically suppressed unless debug mode is enabled.

## Creating Projects

### Interactive Wizard Mode
Run `bablib create` without arguments to launch the interactive wizard:
```bash
$ bablib create

╭─ Create Documentation Project ─────────────────────╮
│                                                     │
│ Follow the prompts to complete the setup.          │
│ Press Ctrl+C to cancel at any time.               │
╰─────────────────────────────────────────────────────╯

Step 1/4 ████░░░░░░ 25%

Project Name
Unique name for your documentation project (letters, numbers, hyphens)
> my-docs

Documentation URL
URL of the documentation to crawl (e.g., https://docs.example.com)
> https://docs.example.com

Crawl Depth (default: 2)
How many levels deep to crawl (1-10, default: 2)
> 3

Embedding Model (default: mxbai-embed-large)
Model for generating embeddings (default: mxbai-embed-large)
>

╭─ Review Your Settings ──────────────────────────────╮
│ Setting           Value                             │
│ ──────────────────────────────────────────────────  │
│ Name              my-docs                           │
│ Url               https://docs.example.com         │
│ Depth             3                                 │
│ Model             mxbai-embed-large                │
╰──────────────────────────────────────────────────────╯

Create project with these settings? [Y/n]: y
✓ Project 'my-docs' created successfully
```

### Direct Command Mode
Provide arguments to skip the wizard:
```bash
$ bablib create my-project --url https://docs.example.com --depth 2
✓ Project 'my-project' created successfully
```

## Crawling Documentation

### Single Project Crawl
```bash
$ bablib crawl my-project --max-pages 100
```

### Update Existing Project
Recrawl an existing project:
```bash
$ bablib crawl --update my-project
```

### Progress Visualization
Crawling shows a two-phase progress bar:
```bash
$ bablib crawl my-project
Crawling my-project...

Analyzing headers   ████████░░ 80% 40/50 0:00:05
Crawling content    ██████░░░░ 60% 30/50 0:00:15

Phase Summary
─────────────────────────────────────────────────────
Phase               Completed  Total  Duration (s)
Analyzing Headers   50         50     5.23
Crawling Content    50         50     23.45

✓ Crawl completed successfully

Project Status:
  Documents: 50
  Embeddings: 500
```

### Debug Mode Crawling
Use `--debug` with crawl to see detailed output:
```bash
$ bablib crawl my-project --debug
[DEBUG] Starting crawl for my-project
[DEBUG] Fetching: https://docs.example.com/index.html
[DEBUG] Found 15 links
[DEBUG] Processing: https://docs.example.com/guide.html
...
```

## Batch Operations

### Update All Projects
Recrawl all existing projects sequentially:
```bash
$ bablib crawl --update --all
Starting batch crawl for 5 projects

Processing project-1 (1/5)
Processing project-2 (2/5)
Processing project-3 (3/5)
Processing project-4 (4/5)
Processing project-5 (5/5)

Batch Crawl Complete
  Succeeded: 4
  Failed: 1
  Total pages: 245

Failed projects:
  - project-3: Network timeout
```

### Continue on Error
Batch operations continue even if individual projects fail:
- Each project is attempted regardless of previous failures
- Failed projects are reported in the summary
- Projects start immediately after the previous one completes (no artificial delay)

## Progress Visualization

### Two-Phase Progress
Crawl operations show two distinct phases:
1. **Header Analysis**: Quick scan of document structure
2. **Content Crawling**: Full content extraction and processing

### Conditional Display
Progress bars are hidden when:
- `--debug` flag is active (shows detailed logs instead)
- `--no-progress` flag is used
- Output is piped to another command
- `--json` format is selected

### Update Frequency
Progress updates every 500ms for smooth visualization without overwhelming the terminal.

## Error Reporting

### Automatic Error Collection
During crawling, all errors are automatically collected:
- URL that caused the error
- Error type (NETWORK, TIMEOUT, PARSE, RATE_LIMIT, etc.)
- Error message and code
- Retry attempts

### Error Report Generation
When errors occur, a report is generated:
```bash
$ bablib crawl my-project
...
⚠ Crawl completed with 5 errors
Error report saved to: ~/.local/share/bablib/projects/my-project/reports/report_20240126_101523.txt
Review errors: open ~/.local/share/bablib/projects/my-project/reports/report_20240126_101523.txt
```

### Report Structure
Error reports contain:
```
================================================================================
CRAWL REPORT - my-project
================================================================================
Report ID: 123e4567-e89b-12d3-a456-426614174000
Timestamp: 2024-01-26T10:15:23
Status: PARTIAL
Duration: 45.67 seconds

STATISTICS:
----------------------------------------
Total Pages: 100
Successful: 95
Failed: 5
Embeddings Created: 950

ERROR SUMMARY:
----------------------------------------
Total Errors: 5
Unique URLs: 5

Errors by Type:
  NETWORK: 3
  TIMEOUT: 2

DETAILED ERRORS:
----------------------------------------

[1] URL: https://docs.example.com/broken
    Type: NETWORK
    Message: Connection refused
    Time: 2024-01-26T10:15:10

[2] URL: https://docs.example.com/slow
    Type: TIMEOUT
    Message: Request timeout after 30 seconds
    Time: 2024-01-26T10:15:20
    Retries: 3

================================================================================
END OF REPORT
```

### Report Storage
- Reports are stored in project-specific directories
- Path: `~/.local/share/bablib/projects/{name}/reports/`
- One report file per project (overwritten on recrawl)
- Both JSON and text formats are saved

## Global Options

### Output Formats
- `--json`: Machine-readable JSON output
- `--no-color`: Disable terminal colors
- Default: Human-readable formatted output

### Verbosity Control
- `--quiet, -q`: Suppress non-essential output
- `--verbose, -v`: Show additional information
- `--debug`: Show all debug information

### Progress Control
- `--no-progress`: Disable progress indicators
- Progress is automatically hidden when output is piped

## Tips and Best Practices

1. **Use the wizard for first-time setup**: It guides you through all options
2. **Enable debug for troubleshooting**: `--debug` reveals what's happening
3. **Review error reports**: They contain valuable debugging information
4. **Batch updates overnight**: Use `--update --all` for maintenance
5. **Quote URLs with special characters**: `bablib create proj -u "https://example.com?param=value"`

## Environment Variables

```bash
# Set default debug mode
export BABLIB_DEBUG=true

# Set custom data directory
export BABLIB_DATA_DIR=/custom/path

# Set log level
export BABLIB_LOG_LEVEL=DEBUG
```

## Examples

### Complete Project Setup
```bash
# Create project interactively
bablib create

# Or create directly
bablib create my-docs --url https://docs.example.com --depth 3

# Initial crawl
bablib crawl my-docs --max-pages 500

# Search documentation
bablib search "authentication" --project my-docs
```

### Maintenance Workflow
```bash
# List all projects
bablib list

# Update specific project
bablib crawl --update my-docs

# Update all projects
bablib crawl --update --all

# Check status
bablib status
```

### Debugging Issues
```bash
# Enable debug output
bablib --debug crawl my-docs

# Check error reports
ls ~/.local/share/bablib/projects/my-docs/reports/

# View latest report
cat ~/.local/share/bablib/projects/my-docs/reports/report_latest.txt
```