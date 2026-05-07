# Things 3 MCP Server - AI Assistant Instructions

## Project Overview

**Things 3 MCP Server** - A Model Context Protocol server that enables AI assistants to interact with Things 3 via AppleScript on macOS.

### Current Version: v1.4.4

Highlights of recent stable behavior:
- **🏷️ Tag Management** - Robust comma-separated tag handling across all tag operations
- **⚡ Bulk Operations** - Multi-field updates apply all fields atomically per todo
- **📅 Date Scheduling** - Reliable scheduling with `today`, `tomorrow`, `someday`, or `YYYY-MM-DD`
- **✅ Tool Annotations** - All 37 tools declare `readOnlyHint`/`destructiveHint`/`title` for MCP-client UIs (since v1.5-pending; see commit `64c82a1`)
- **📊 Context Optimization** - Response modes (`auto`/`summary`/`minimal`/`standard`/`detailed`/`raw`) for budget control

### Architecture
- **Framework**: FastMCP 2.0+ (3.2.4 in current venv)
- **Runtime**: Python 3.8+ (3.13 in current venv)
- **Integration**: AppleScript via subprocess + Things URL scheme for checklists
- **Testing**: pytest with mocked AppleScript operations (469 unit tests)
- **Platform**: macOS 12.0+ with Things 3 installed

### Related Docs
- `docs/ARCHITECTURE.md` — system layout
- `docs/BULK_OPERATIONS_GUIDE.md` — patterns for bulk_*
- `docs/USER_EXAMPLES.md` — end-user-style example calls
- `docs/TROUBLESHOOTING.md` — common runtime issues
- `docs/REFACTORING_PLAN.md` — internal-only 10-week quality plan
- `docs/V2_API_MIGRATION.md` — proposal for native list parameters (not scheduled)

## Development Guidelines

### Code Style
- Keep it simple and maintainable - no over-engineering
- Follow existing patterns in the codebase
- Add type hints to all new functions
- Document with clear docstrings (Google style)

### Testing Requirements
```bash
# Run tests before committing
pytest                          # Run all tests
pytest tests/unit/              # Unit tests only
pytest tests/integration/       # Integration tests
pytest --cov=src/things_mcp     # With coverage
```

### File Organization
```
src/things_mcp/     # Source code
tests/              # Test files  
docs/               # Documentation
```

### AppleScript Integration

When working with AppleScript:
1. **Escape quotes properly** - Use `_escape_applescript_string()` 
2. **Handle errors gracefully** - AppleScript can fail silently
3. **Test with real Things 3** - Mock tests don't catch all issues
4. **Check permissions** - Automation access must be granted

Example pattern:
```python
script = f'''
tell application "Things3"
    set newTodo to make new to do with properties {{name:"{escaped_title}"}}
    return id of newTodo
end tell
'''
result = self.applescript_manager.execute_script(script)
```

### Common Issues & Solutions

1. **Tag must exist first**: AI cannot create tags automatically - use `get_tags()` to check available tags
2. **Large data timeouts**: Use response modes (summary, minimal) and pagination
3. **Date formats**: Always use ISO 8601 format (YYYY-MM-DD) for best reliability
4. **Permission errors**: System Settings → Privacy & Security → Automation → Enable Things 3 access

### API Coverage Status
- **Implemented**: 37 tools (~45% of AppleScript API)
- **Tested**: 469 unit tests + integration tests
- **Roadmap**: See `docs/V2_API_MIGRATION.md` for the proposed v2 API; `docs/REFACTORING_PLAN.md` for internal cleanup
- **Priority**: Daily workflow operations (read, list, create, update, move, search)

### Adding a New Tool

When registering a new `@self.mcp.tool()` in `server.py`:
- Use the helpers `_read_tool_annotations(title)` or `_write_tool_annotations(title, destructive=, idempotent=)` (defined at `server.py:33-55`). Never inline annotation dicts — that pattern was deliberately removed.
- Single-line imperative docstring; param docs belong in `Field(description=...)`.
- Bump `EXPECTED_TOOL_COUNT` (and update `DESTRUCTIVE_TOOLS` if applicable) in `tests/unit/test_annotations.py`, otherwise the regression suite fails.

### Why Some Params Use Comma-Separated Strings

`tags`, `todo_ids`, etc. accept comma-separated strings (e.g. `tags="work,urgent"`) rather than native arrays. This is intentional and load-bearing for v1.x backward compatibility. The migration proposal lives in `docs/V2_API_MIGRATION.md` — out of scope for any non-major change.

## 🏷️ Tag Management

### Working with Tags

**Important**: Tags must be created in Things 3 before they can be used via the API. The AI assistant cannot create tags programmatically.

```python
# Get all available tags
tags = get_tags()  # Returns count-only by default
tags = get_tags(include_items=true)  # Returns full item lists

# Get todos with a specific tag
work_todos = get_tagged_items(tag="Work")
urgent_todos = get_tagged_items(tag="urgent")
```

### Adding Tags

```python
# Single tag
add_tags(todo_id="abc123", tags="urgent")

# Multiple tags (comma-separated, no spaces)
add_tags(todo_id="abc123", tags="work,urgent,review")

# When creating todos
add_todo(
    title="Review proposal",
    tags="work,urgent,review",  # Comma-separated
    when="today"
)

# Bulk update with tags
bulk_update_todos(
    todo_ids="id1,id2,id3",
    tags="urgent,Q4"  # Replaces existing tags
)
```

### Removing Tags

```python
# Remove single tag
remove_tags(todo_id="abc123", tags="urgent")

# Remove multiple tags (comma-separated, no spaces)
remove_tags(todo_id="abc123", tags="urgent,review,old-tag")

# Tag names are case-sensitive
remove_tags(todo_id="abc123", tags="Work")   # Removes "Work"
remove_tags(todo_id="abc123", tags="work")   # Removes "work" (different tag)
```

### Tag Best Practices

1. **Check Available Tags First**:
   ```python
   # See what tags exist
   tags = get_tags()
   # If tag doesn't exist, ask user to create it in Things 3
   ```

2. **Format Requirements**:
   - Use comma separation: `"tag1,tag2,tag3"`
   - No spaces after commas: `"work,urgent"` not `"work, urgent"`
   - Case-sensitive: `"Work"` ≠ `"work"`

3. **Tag Filtering**:
   - Non-existent tags are silently filtered (no error)
   - Only existing tags will be added/removed
   - Use `get_tags()` to validate tags exist

4. **Tag Search**:
   ```python
   # Search by tag
   search_advanced(tag="urgent", status="incomplete")

   # Get all items with specific tag
   get_tagged_items(tag="work")
   ```

## 🔧 Tool Usage Best Practices

### Response Mode Selection

When working with retrieval tools (`get_todos`, `search_todos`, list tools), use the `mode` parameter for optimal context usage:

**Available Modes:**
- `auto` - Automatically selects optimal mode based on data size (recommended for unknown datasets)
- `summary` - Returns count and preview only (best for large collections)
- `minimal` - Returns essential fields only (IDs, titles, status)
- `standard` - Returns common fields (default for most operations)
- `detailed` - Returns all fields (use only when needed)
- `raw` - Returns unfiltered data

**Workflow Examples:**

1. **Daily Review**
   ```
   get_today(mode='standard', limit=20)
   ```

2. **Project Analysis**
   ```
   # First get overview
   get_todos(project_uuid='...', mode='summary')
   # Then drill down to specifics
   get_todos(project_uuid='...', mode='detailed', limit=10)
   ```

3. **Bulk Operations**
   ```
   # Get IDs efficiently
   search_todos(query='overdue', mode='minimal', limit=100)
   # Perform bulk update
   bulk_update_todos(todo_ids='...', completed='true')
   ```

### Context Budget Guidelines

- **Standard mode**: ~1KB per item
- **Minimal mode**: ~50 bytes per item
- **Summary mode**: Fixed ~200 bytes total
- For 100+ items, always start with `mode='summary'` or `mode='minimal'`

### Performance Tips

1. **Use specific list tools** instead of filtering `get_todos`:
   - `get_today()` is faster than `get_todos()` with date filtering
   - `get_tagged_items(tag='work')` is faster than searching

2. **Batch operations** when possible:
   - Use `bulk_update_todos` for multiple todos (supports multi-field updates)
   - Use `bulk_move_records` instead of multiple `move_record` calls
   - Optimal batch size: 2-50 todos per operation

3. **Multi-field bulk updates** (efficient for large updates):
   ```python
   # Update multiple fields in one operation
   bulk_update_todos(
       todo_ids="id1,id2,id3,id4,id5",
       tags="urgent,Q4",
       when="today",
       notes="Updated in batch review"
   )
   ```

## 📁 Hierarchical Organization (Projects & Areas)

### Organizational Structure

Things 3 supports a 4-level hierarchy:
```
Areas (Life/Work Domains)
└── Projects (Time-bound outcomes)
    └── Todos (Action items)
        └── Checklist Items (Sub-tasks)
```

### Working with Areas

Areas represent life domains (Work, Personal, Learning, etc.):

```python
# Get all areas
areas = get_areas(mode='summary')  # Quick overview
areas = get_areas(mode='standard')  # Full list
areas = get_areas(include_items=true, mode='detailed')  # With projects and todos

# Create project in specific area
add_project(
    title="New Project",
    area_id="abc123",  # Recommended - more reliable
    deadline="2025-12-31"
)

# Or use area name
add_project(
    title="New Project",
    area_title="Personal",  # Convenient but requires unique names
    deadline="2025-12-31"
)
```

### Working with Projects

Projects are time-bound outcomes with associated tasks:

```python
# Create project
project_id = add_project(
    title="Website Redesign",
    area_title="Work",
    deadline="2025-12-31",
    tags="high-priority,design",
    notes="Complete redesign of company website"
)

# Add todos to project (must be done separately)
add_todo(title="Research competitors", list_id=project_id, heading="Research")
add_todo(title="Create wireframes", list_id=project_id, heading="Design")
add_todo(title="Implement homepage", list_id=project_id, heading="Development")

# Update project
update_project(
    id=project_id,
    deadline="2026-01-15",
    tags="urgent,design,review-needed"
)

# Get projects
get_projects(mode='summary')  # Count and preview
get_projects(mode='minimal')  # IDs and names only
get_projects(mode='standard')  # Full details
```

### Moving Todos Between Projects

```python
# Move single todo
move_record(
    todo_id="todo123",
    destination_list="project:project456"
)

# Move multiple todos (bulk operation - much faster)
bulk_move_records(
    todo_ids="todo1,todo2,todo3",
    destination="project:project456",
    preserve_scheduling=true
)
```

### Destination Formats

| Target | Format | Example |
|--------|--------|---------|
| Inbox | `"inbox"` | `move_record(todo_id="123", destination_list="inbox")` |
| Today | `"today"` | `move_record(todo_id="123", destination_list="today")` |
| Anytime | `"anytime"` | `move_record(todo_id="123", destination_list="anytime")` |
| Someday | `"someday"` | `move_record(todo_id="123", destination_list="someday")` |
| Project | `"project:{id}"` | `move_record(todo_id="123", destination_list="project:xyz")` |

### Status Filtering

The `get_todos()` function supports filtering by completion status:

```python
# Get incomplete todos (default behavior)
get_todos(project_uuid="abc123")
get_todos(project_uuid="abc123", status="incomplete")

# Get ALL todos (completed + incomplete + canceled)
get_todos(project_uuid="abc123", status=None)

# Get only completed todos
get_todos(project_uuid="abc123", status="completed")

# Get only canceled todos
get_todos(project_uuid="abc123", status="canceled")

# Works without project filter too
get_todos(status="completed")  # All completed todos
get_todos(status=None)  # All todos regardless of status
```

**Status Parameter Options:**
- `'incomplete'` (default) - Only active, uncompleted todos
- `'completed'` - Only completed todos
- `'canceled'` - Only canceled todos
- `None` - All todos regardless of status

This feature is useful for:
- Reviewing completed work in a project
- Analyzing canceled todos
- Getting complete project history
- Status-based reporting and analytics

### Checklist Support ✅

**Checklist items are now fully supported** via the Things 3 URL scheme API. The server automatically uses the URL scheme when checklist items are provided.

#### Creating Todos with Checklists

```python
# Create todo with checklist items
add_todo(
    title="Grocery Shopping",
    notes="Weekly shopping list",
    checklist_items=["Milk", "Bread", "Eggs", "Butter"],  # List of strings
    when="today"
)

# With project and tags
add_todo(
    title="Release v2.0",
    checklist_items=["Run tests", "Update docs", "Create changelog", "Tag release"],
    list_id="project123",
    tags="work,release",
    deadline="2025-12-31"
)
```

#### Managing Checklist Items

```python
# Add items to existing todo (appends to end)
add_checklist_items(
    todo_id="abc123",
    items=["New item 1", "New item 2"]
)

# Prepend items to beginning
prepend_checklist_items(
    todo_id="abc123",
    items=["Urgent item", "High priority"]
)

# Replace all checklist items
replace_checklist_items(
    todo_id="abc123",
    items=["Item 1", "Item 2", "Item 3"]
)

# Clear all checklist items
replace_checklist_items(
    todo_id="abc123",
    items=[]  # Empty list clears checklist
)
```

**Format Requirements:**
- Items are passed as a list of strings: `["item1", "item2", "item3"]`
- Maximum 100 checklist items per todo
- Items can be marked complete/incomplete in Things 3 UI

**Implementation Details:**
- Checklists use Things URL scheme API (not AppleScript)
- URL scheme is automatically used when `checklist_items` parameter is provided
- Todo ID is retrieved after creation by searching for the newly created todo
- Non-checklist todos still use faster AppleScript approach

### Known Limitations

1. **Project include_items context explosion**: ⚠️ **NEVER use `get_projects(include_items=true)`** - generates 252K+ tokens for 73 projects, exceeding context limits. Always use `get_projects(mode='summary')` first, then query specific projects.

**Workarounds:**
- Use `get_projects(mode='minimal')` to get IDs, then query specific projects
- Never use `include_items=true` - causes context overflow

### Hierarchical Best Practices

1. Use areas for life domains (Work, Personal, Learning)
2. Use projects for time-bound outcomes with clear deadlines
3. Use headings within projects to organize phases
4. Start with `mode='summary'` for large project lists
5. Use `area_id` instead of `area_title` for reliability
6. Batch todo moves with `bulk_move_records()`
7. Create tags in Things 3 before using in API

**For Complete Details:** See `docs/USER_EXAMPLES.md` and `docs/BULK_OPERATIONS_GUIDE.md`

### Error Prevention

1. **Tags must exist** - AI cannot create tags automatically
   - Use `get_tags()` to see available tags
   - Ask user to create new tags if needed
   - Tag names are case-sensitive: `"Work"` ≠ `"work"`
   - Use comma-separated format: `"tag1,tag2"` not `"tag1, tag2"`

2. **Date formats** - Use consistent formats:
   - Dates: `YYYY-MM-DD` or `'today'`, `'tomorrow'`, `'someday'`

3. **Limits** - Respect parameter limits:
   - Search results: max 500
   - Logbook: max 100
   - Date ranges: max 365 days
   - Bulk operations: optimal 2-50 todos

4. **Bulk operations** - Multi-field updates:
   - All specified fields are applied to each todo
   - Fields: title, notes, when, deadline, tags, completed, canceled
   - Format IDs as comma-separated: `"id1,id2,id3"`

## ⚠️ Common Pitfalls & Solutions

> Tag-formatting rules (no spaces after comma, case-sensitive, must pre-exist) live under [Tag Management](#-tag-management) — not duplicated here.

### 1. Bulk Update Field Ordering

**Problem**: Assuming field order matters (it doesn't)
```python
# ✅ Both work identically - all fields applied
bulk_update_todos(todo_ids="1,2,3", tags="urgent", when="today")
bulk_update_todos(todo_ids="1,2,3", when="today", tags="urgent")

# All specified fields are applied to each todo
```

### 2. Multi-Field vs Single-Field Updates

**Problem**: Using single updates when bulk would be faster
```python
# ❌ SLOW - multiple API calls
for todo_id in ["1", "2", "3"]:
    update_todo(id=todo_id, tags="urgent")
    update_todo(id=todo_id, when="today")

# ✅ FAST - single bulk operation
bulk_update_todos(
    todo_ids="1,2,3",
    tags="urgent",
    when="today"
)
```

### 3. Project Creation with Initial Todos

**Best Practice**: Use the `todos` parameter for efficient project creation with initial tasks
```python
# ✅ RECOMMENDED: Create project with todos in one call
project_id = add_project(
    title="My Project",
    deadline="2025-12-31",
    todos="Task 1\nTask 2\nTask 3"  # Creates all 3 todos!
)

# ✅ ALTERNATIVE: Add todos separately (useful for dynamic lists)
project_id = add_project(title="My Project", deadline="2025-12-31")
add_todo(title="Task 1", list_id=project_id)
add_todo(title="Task 2", list_id=project_id)
add_todo(title="Task 3", list_id=project_id)
```

**Note**: The `todos` parameter accepts newline-separated todo titles and creates them atomically with the project.

### 4. Large Dataset Queries

**Problem**: Retrieving too much data at once
```python
# ❌ BAD - retrieves all todos with full details
all_todos = get_todos(mode='detailed')  # Could be 1000+ items

# ✅ GOOD - use summary first, then drill down
summary = get_todos(mode='summary')  # Just count and preview
# Then get specific subset:
today = get_today(mode='standard', limit=20)
```

### Commit Guidelines
- Make frequent, small commits
- Use clear commit messages
- Run tests before committing
- Update documentation for API changes

## Release Process

When creating a new release, follow these steps to ensure version consistency across all files:

### 1. Update Version Numbers

**Critical Files (MUST update):**

```bash
# 1. Update package version
# File: pyproject.toml (line 7)
version = "X.Y.Z"

# 2. Update runtime version
# File: src/things_mcp/__init__.py (line 3)
__version__ = "X.Y.Z"

# 3. Update CHANGELOG
# File: CHANGELOG.md (top of file)
## [X.Y.Z] - YYYY-MM-DD

### Fixed
- Bug fix description

### Added
- New feature description

### Changed
- Change description
```

### 2. Commit and Tag

```bash
# Run tests first
pytest

# Commit changes
git add pyproject.toml src/things_mcp/__init__.py CHANGELOG.md
git commit -m "Release vX.Y.Z - Brief description"

# Push to GitHub
git push origin main

# Create and push tag
git tag vX.Y.Z
git push origin vX.Y.Z
```

### 3. Create GitHub Release

```bash
# Create release with notes from CHANGELOG
gh release create vX.Y.Z \
  --title "vX.Y.Z - Release Title" \
  --notes "$(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md | head -n -1)"
```

### 4. Publish to PyPI

```bash
# Build distribution packages
python -m build

# Upload to PyPI
python -m twine upload dist/mcp_server_things-X.Y.Z*
```

### Version Consistency Notes

- **pyproject.toml** - Package version for pip/PyPI
- **src/things_mcp/__init__.py** - Runtime version (used by server.py)
- **CHANGELOG.md** - Version history with dates
- Version is automatically synced: `__version__` is imported by server.py and reported via `get_server_capabilities()`
- No need to update version in documentation examples (README.md, CONTRIBUTING.md) - those are placeholders

### Release Checklist

- [ ] All tests pass (`pytest`)
- [ ] Version updated in `pyproject.toml`
- [ ] Version updated in `src/things_mcp/__init__.py`
- [ ] CHANGELOG.md updated with date and changes
- [ ] Committed with descriptive message
- [ ] Pushed to GitHub
- [ ] Git tag created and pushed
- [ ] GitHub release created
- [ ] Published to PyPI
- [ ] Verify version reporting: AI should report correct version when queried

## Code Quality Improvements

### Active Refactoring Plan

**Status:** Planning Phase
**Document:** `docs/REFACTORING_PLAN.md`

A comprehensive 10-week, 8-phase refactoring plan has been created to improve code quality:

**Current Issues:**
- 5 bare `except:` blocks hiding errors
- 19 functions >100 lines (largest: 214 lines)
- 4 files >1,300 lines (largest: 1,657 lines)
- 31 duplicate AppleScript invocations
- Complex 193-line string parser

**Target Improvements:**
- Zero bare except blocks (specific exception types + logging)
- All functions <100 lines (target: 80)
- All files <1,000 lines (target: 500)
- Consolidated AppleScript patterns via templates
- State machine-based parser

**Phased Approach:**
1. **Phase 1 (Week 1):** Fix bare except blocks - LOW RISK
2. **Phase 2 (Weeks 2-3):** Parser refactoring - HIGH RISK, feature-flagged
3. **Phase 3 (Weeks 4-5):** Function decomposition - MEDIUM RISK
4. **Phase 4 (Week 6):** File organization - MEDIUM RISK
5. **Phase 5 (Week 7):** Consolidate AppleScript patterns - LOW RISK
6. **Phase 6 (Week 8):** Error handling improvements - LOW RISK
7. **Phase 7 (Week 9):** Documentation - LOW RISK
8. **Phase 8 (Week 10):** Performance testing - LOW RISK

**Constraints:**
- ✅ 100% backwards compatibility (no breaking changes)
- ✅ All 330+ tests must continue to pass
- ✅ No performance regressions >10%
- ✅ Incremental commits (each passes tests)

**For Swarm Implementation:**
- See `docs/REFACTORING_PLAN.md` for detailed task breakdown
- Each phase has specific deliverables and validation steps
- Parallel execution possible for Phase 1, 3, 4 tasks
- Feature flags for high-risk changes (Phase 2)

When implementing refactoring tasks, always:
1. Read the detailed task specification in REFACTORING_PLAN.md
2. Run tests before making changes
3. Make minimal, focused changes
4. Run full test suite after changes
5. Commit only if all tests pass

## Important Reminders
- Never hardcode authentication tokens
- Keep root directory clean (use appropriate subdirectories)
- Prefer editing existing files over creating new ones
- Test with actual Things 3 before marking features complete
- When we add new capabilities, we need to always be sure to "advertise them" to the AI using the MCP server