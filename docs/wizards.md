# Setup Wizards User Guide

**Bablib Interactive Setup Wizards**

Setup wizards provide step-by-step guided configuration for shelves, boxes, and MCP servers. Launch wizards using the `--init` or `-i` flag on any creation command.

## Quick Start

```bash
# Launch shelf wizard during creation
bablib shelf create my-docs --init

# Launch box wizard during creation
bablib box create web-docs --type drag --init

# Launch MCP server wizard
bablib serve --init
```

## Shelf Setup Wizard

**Purpose**: Configure shelf metadata, auto-fill behavior, and default settings for new boxes.

### Steps

**Step 1: Description**
```
Enter shelf description (optional):
> Main project documentation and API references
```
- Optional text field up to 500 characters
- Helps organize and identify shelf purpose
- Press Enter to skip

**Step 2: Auto-Fill Configuration**
```
Auto-fill empty boxes when accessed? (y/n): y
```
- `y`: Automatically prompt to fill content when accessing empty boxes
- `n`: Manual filling only via `bablib fill` command
- Recommended: `y` for active documentation shelves

**Step 3: Default Box Type**
```
Default box type for new boxes:
  1. drag - Website crawler
  2. rag - Document uploader
  3. bag - File storage
→ 1
```
- Use arrow keys (↑/↓) or numbers (1-3) to select
- Sets default type for boxes created without `--type` flag
- Can be overridden per-box

**Step 4: Tags**
```
Add tags (comma-separated, optional):
> docs, api, python, main
```
- Optional comma-separated tag list
- Helps filter and organize shelves
- Press Enter to skip

**Step 5: Confirmation**
```
Review configuration:
  Description: Main project documentation and API references
  Auto-fill: Enabled
  Default type: drag
  Tags: docs, api, python, main

Apply this configuration? (y/n): y
```
- Review all collected settings
- `y`: Apply and create shelf
- `n`: Cancel wizard and return to command prompt

### Example Session

```bash
$ bablib shelf create python-docs --init

Setting up shelf: python-docs

Step 1/5: Description
Enter shelf description (optional):
> Python standard library documentation

Step 2/5: Auto-Fill
Auto-fill empty boxes when accessed? (y/n): y

Step 3/5: Default Box Type
Default box type for new boxes:
  1. drag - Website crawler
  2. rag - Document uploader
  3. bag - File storage
→ 1

Step 4/5: Tags
Add tags (comma-separated, optional):
> python, stdlib, reference

Step 5/5: Confirmation
Review configuration:
  Description: Python standard library documentation
  Auto-fill: Enabled
  Default type: drag
  Tags: python, stdlib, reference

Apply this configuration? (y/n): y

✓ Shelf 'python-docs' created and configured successfully!

Next steps:
  - Create boxes: bablib box create <name> --shelf python-docs
  - View shelf: bablib shelf python-docs
```

## Box Setup Wizard

**Purpose**: Configure box-specific settings based on box type (drag/rag/bag).

### Steps

**Step 1: Type Confirmation**
```
Confirm box type 'drag' - Website crawler? (y/n): y
```
- Confirms the box type specified in creation command
- Provides description of selected type
- Type-specific wizard steps follow

**Step 2: Description**
```
Enter box description (optional):
> Django framework documentation
```
- Optional text field up to 500 characters
- Describes box content and purpose

**Step 3: Auto-Process** (Type-Specific)
```
Auto-process content on fill? (y/n): y
```
- `y`: Automatically chunk and vectorize content when added
- `n`: Manual processing via separate command
- Recommended: `y` for most use cases

**Step 4: Type-Specific Settings**

**For Drag Boxes (Website Crawler)**:
```
Maximum pages to crawl (default: 100):
> 500

Rate limit (requests/second, default: 1.0):
> 2.0

Maximum crawl depth (default: 3):
> 5
```

**For Rag Boxes (Document Uploader)**:
```
File patterns (comma-separated, default: *.pdf,*.txt,*.md):
> *.pdf, *.docx, *.txt

Chunk size (characters, default: 500):
> 1000

Chunk overlap (characters, default: 50):
> 100
```

**For Bag Boxes (File Storage)**:
```
File type filter (comma-separated, optional):
> json, yaml, toml

Process recursively? (y/n): y

Exclude patterns (comma-separated, optional):
> node_modules, .git, __pycache__
```

**Step 5: Initial Content** (Optional)
```
Provide initial content source? (y/n): y

For drag: Enter website URL:
> https://docs.djangoproject.com

For rag: Enter file path:
> /path/to/documents/

For bag: Enter content directory:
> /path/to/files/
```

**Step 6: Confirmation**
```
Review configuration:
  Type: drag (Website crawler)
  Description: Django framework documentation
  Auto-process: Enabled
  Max pages: 500
  Rate limit: 2.0/s
  Depth: 5
  Initial source: https://docs.djangoproject.com

Apply this configuration? (y/n): y
```

### Example Session

```bash
$ bablib box create django-docs --type drag --shelf python-docs --init

Setting up box: django-docs

Step 1/6: Type Confirmation
Confirm box type 'drag' - Website crawler? (y/n): y

Step 2/6: Description
Enter box description (optional):
> Django web framework documentation

Step 3/6: Auto-Process
Auto-process content on fill? (y/n): y

Step 4/6: Crawler Settings
Maximum pages to crawl (default: 100):
> 500

Rate limit (requests/second, default: 1.0):
> 2.0

Maximum crawl depth (default: 3):
> 5

Step 5/6: Initial Content
Provide initial content source? (y/n): y
Enter website URL:
> https://docs.djangoproject.com

Step 6/6: Confirmation
Review configuration:
  Type: drag (Website crawler)
  Description: Django web framework documentation
  Auto-process: Enabled
  Max pages: 500
  Rate limit: 2.0/s
  Depth: 5
  Initial source: https://docs.djangoproject.com

Apply this configuration? (y/n): y

✓ Box 'django-docs' created and configured successfully!
⏳ Starting initial crawl of https://docs.djangoproject.com...

Crawling progress: 45/500 pages | Rate: 2.0/s | Depth: 3/5
```

## MCP Server Setup Wizard

**Purpose**: Configure MCP server ports and behavior for AI assistant integration.

### Steps

**Step 1: Read-Only Server**
```
Enable read-only MCP server? (y/n): y
```
- Provides safe read access to shelves/boxes for AI assistants
- Recommended: `y` for most users

**Step 2: Read-Only Port**
```
Read-only server port (default: 9383):
> 9383
```
- Port for read-only MCP server
- Must be between 1024-65535
- Checks for port conflicts

**Step 3: Admin Server**
```
Enable admin MCP server? (y/n): y
```
- Provides full command execution for AI assistants
- Localhost-only for security
- Recommended: `y` for development, `n` for production

**Step 4: Admin Port**
```
Admin server port (default: 9384):
> 9384
```
- Port for admin MCP server (if enabled)
- Must be different from read-only port
- Checks for port conflicts

**Step 5: Auto-Start**
```
Auto-start MCP servers with system? (y/n): n
```
- `y`: Servers start automatically on system boot
- `n`: Manual start via `bablib serve`
- Recommended: `n` for most users

**Step 6: Confirmation**
```
Review configuration:
  Read-only server: Enabled on port 9383
  Admin server: Enabled on port 9384 (localhost only)
  Auto-start: Disabled

Apply this configuration? (y/n): y
```

### Example Session

```bash
$ bablib serve --init

Setting up MCP servers

Step 1/6: Read-Only Server
Enable read-only MCP server? (y/n): y

Step 2/6: Read-Only Port
Read-only server port (default: 9383):
> 9383

Step 3/6: Admin Server
Enable admin MCP server? (y/n): y

Step 4/6: Admin Port
Admin server port (default: 9384):
> 9384

Step 5/6: Auto-Start
Auto-start MCP servers with system? (y/n): n

Step 6/6: Confirmation
Review configuration:
  Read-only server: Enabled on port 9383
  Admin server: Enabled on port 9384 (localhost only)
  Auto-start: Disabled

Apply this configuration? (y/n): y

✓ MCP servers configured successfully!
⏳ Starting servers...

Read-only server running at http://0.0.0.0:9383
Admin server running at http://127.0.0.1:9384

Connection info for AI assistants:
  Claude Code: Add MCP server configuration to ~/.config/claude-code/mcp.json
  See: /path/to/mcp/claude-config.json
```

## Navigation

All wizards support universal navigation:

### Keyboard Shortcuts
- **↑/↓ arrows**: Navigate between choices
- **j/k**: Vim-style navigation
- **1-9**: Direct number selection (where applicable)
- **Enter**: Confirm selection or input
- **Ctrl+C**: Cancel wizard
- **?**: Show help

### Input Types
- **Choice**: Use arrows/numbers to select from list
- **Text**: Type freely, press Enter to confirm
- **Boolean**: Press `y` or `n` (never numbered)
- **File Path**: Type path with tab-completion support
- **URL**: Type URL with validation

## Wizard State Management

Wizards maintain state throughout the session:

### Session Lifecycle
1. **Started**: Wizard session created with unique ID
2. **In Progress**: User navigates through steps
3. **Completed**: Configuration applied successfully
4. **Cancelled**: User aborted via Ctrl+C

### Timeout Behavior
- Wizards timeout after **30 minutes** of inactivity
- Partial data is **not saved** on timeout
- Restart wizard to begin fresh session

### Interruption Recovery
```bash
# If wizard is interrupted (network failure, terminal crash)
# Restart the same command to begin a fresh session:
bablib shelf create my-docs --init

# Previous incomplete sessions are automatically cleaned up
```

## Tips and Best Practices

### For Shelves
- Use descriptive names: `python-docs` not `docs1`
- Enable auto-fill for active documentation
- Set default box type based on primary content source
- Use tags for multi-project organization

### For Boxes
- Match box type to content:
  - `drag`: Live websites, API docs, dynamic content
  - `rag`: PDFs, documents, static files
  - `bag`: Configuration files, data files, archives
- Enable auto-process unless manual control needed
- Provide initial source when available to start filling immediately

### For MCP Servers
- Always enable read-only server for AI assistants
- Only enable admin server if needed for automation
- Use default ports unless conflicts exist
- Disable auto-start for security and resource control

## Troubleshooting

### Wizard Won't Start
```bash
# Check if wizard is already running
bablib debug wizard-sessions

# Clear stuck sessions
bablib setup --reset-wizards
```

### Invalid Input Errors
- Follow validation hints in error messages
- Use suggested formats or examples
- Skip optional fields if unsure

### Port Conflicts (MCP Wizard)
- Wizard automatically detects port conflicts
- Suggests alternative ports when needed
- Check running services: `lsof -i :9383`

### Timeout Issues
- Complete wizard within 30-minute window
- Restart wizard if interrupted
- No partial data recovery available

## Advanced Usage

### Skipping Wizards
Create entities without wizards by omitting `--init` flag:

```bash
# Create shelf without wizard
bablib shelf create quick-shelf --description "Quick setup"

# Create box without wizard
bablib box create quick-box --type rag --shelf quick-shelf
```

### Programmatic Configuration
Use MCP admin endpoints for automated setup:

```bash
# Via API instead of CLI wizard
curl -X POST http://localhost:9384/admin/context/create-shelf \
  -H "Content-Type: application/json" \
  -d '{
    "name": "api-docs",
    "run_wizard": true,
    "wizard_config": {
      "auto_fill": true,
      "default_box_type": "drag",
      "tags": ["api", "reference"]
    }
  }'
```

### Wizard Sessions via MCP
Start and control wizards through MCP endpoints:

```bash
# Start wizard session
curl -X POST http://localhost:9384/admin/wizards/start \
  -d '{"wizard_type": "shelf", "target_entity": "test-shelf"}'

# Submit step response
curl -X POST http://localhost:9384/admin/wizards/{id}/step \
  -d '{"response": "Test description"}'
```

## Related Commands

- `bablib shelf create <name>` - Create shelf (add `--init` for wizard)
- `bablib box create <name> --type <type>` - Create box (add `--init` for wizard)
- `bablib serve` - Start MCP servers (add `--init` for wizard)
- `bablib setup` - System setup (includes wizard configuration)
- `bablib health` - Check system and services status

## Support

For issues or questions:
- Check logs: `~/.cache/bablib/logs/`
- Debug wizard state: `bablib debug wizard-sessions`
- Report bugs: https://github.com/behemotion/bablib/issues