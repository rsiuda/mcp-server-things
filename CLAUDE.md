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

- **Framework**: FastMCP 2.0+ (3.2.4 in current venv) | **Runtime**: Python 3.8+ (3.13 in venv) | **Platform**: macOS 12.0+ with Things 3
- **Bridge to Things 3**: AppleScript via `subprocess` for most operations; **Things URL scheme** for checklist writes (transparent fallback inside `add_todo`).
- **Reads vs writes**: reads go through the `things.py` library against the Things 3 SQLite DB (fast); writes go through AppleScript / URL scheme (slow, single-threaded, queued).

Layered structure:

```
server.py                 — 37 MCP tools, param validation, context-budget optimization
  └─ tools.py             — ThingsTools facade, dispatches to layer below
       ├─ services/applescript_manager  → subprocess + URL scheme execution
       ├─ services/tag_service          → tag-creation policy enforcement
       ├─ services/validation_service   → date/parameter validation
       └─ scheduling/                   → date strategies, recurring todos, search
```

For deeper detail (parser internals, cache strategy, queue mechanics), see `docs/ARCHITECTURE.md`.

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

Rules that aren't visible from tool signatures:

- **Tags must pre-exist in Things 3.** AI cannot create them via the API by default (controlled by `ai_can_create_tags` in config); ask the user to create unknown tags in the Things 3 UI.
- **Case-sensitive.** `"Work"` and `"work"` are distinct tags.
- **Comma-separated, no spaces.** `tags="work,urgent"` — `tags="work, urgent"` produces a tag literally named `" urgent"` with leading whitespace.
- **Non-existent tags are silently filtered.** No error is raised; call `get_tags()` first if you need certainty.
- **`add_tags` is set-semantic / idempotent** — adding the same tag twice is a no-op. `add_checklist_items` is *not* idempotent (each call appends).

Relevant tools: `get_tags`, `get_tagged_items`, `add_tags`, `remove_tags`, `create_tag`. Signatures live in `server.py`.

## 🔧 Tool Usage Best Practices

### Response modes (`mode` param on retrieval tools)

| Mode | When to use |
|---|---|
| `auto` | Default for unknown dataset sizes — adapts |
| `summary` | Quick count + preview for large collections (>100 items) |
| `minimal` | IDs + titles + status — perfect for "find then bulk-update" workflows |
| `standard` | Common fields — default for daily workflows |
| `detailed` | All fields — use only when you need everything |
| `raw` | Unfiltered passthrough — debugging |

Context budget: standard ~1KB/item, minimal ~50B/item, summary ~200B fixed. For 100+ items, start with `summary` or `minimal`.

### Performance hints not visible from signatures

- **Specific list tools beat filtered `get_todos`.** `get_today()` is faster than `get_todos(when='today')`. `get_tagged_items(tag='work')` is faster than `search_todos(query='work')`.
- **Bulk batch sweet-spot**: 2–50 todos per `bulk_update_todos` / `bulk_move_records` call. Above 50, chunk.
- **Single-field updates in a loop are O(N) AppleScript invocations.** Always prefer bulk.

## 📁 Hierarchical Organization (Projects & Areas)

### Organizational Structure

Things 3 supports a 4-level hierarchy:
```
Areas (Life/Work Domains)
└── Projects (Time-bound outcomes)
    └── Todos (Action items)
        └── Checklist Items (Sub-tasks)
```

### Destination format for `move_record` / `bulk_move_records`

| Target | Format |
|---|---|
| Inbox / Today / Anytime / Someday / Logbook / Upcoming | string literal: `"inbox"`, `"today"`, etc. |
| Project | `"project:{id}"` |
| Area | `"area:{id}"` |

### Status filtering

`get_todos(status=...)` accepts `"incomplete"` (default) / `"completed"` / `"canceled"` / `None` (all).

### Checklist support

Checklists are written via the **Things URL scheme**, not AppleScript — the server transparently switches modes when `checklist_items` is passed to `add_todo`. Max 100 items per todo. To clear: pass `items=[]` to `replace_checklist_items`.

### Patterns not visible from signatures

- **Prefer `area_id` over `area_title`.** Title-based lookup breaks when areas have non-unique names.
- **`add_project(todos="line1\nline2")`** creates the project + initial todos atomically (newline-separated, *not* comma-separated — historic inconsistency, see `docs/V2_API_MIGRATION.md`).
- **Headings** organize todos within a project; passed as `heading="Phase 1"` to `add_todo`.
- **Parameter limits**: search ≤500, logbook ≤100, date-range ≤365 days, bulk ops 2–50 sweet-spot.

### ⚠️ Known context-bombs

- **NEVER `get_projects(include_items=true)`** — generates 252K+ tokens for ~70 projects, exceeds Claude context. Always use `mode='summary'` first, then drill into specific projects via `get_todos(project_uuid=...)`.

For end-user-style examples, see `docs/USER_EXAMPLES.md`. For bulk-op patterns, see `docs/BULK_OPERATIONS_GUIDE.md`.

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

## Release & Refactoring

- **Releasing a new version**: see `docs/RELEASE_PROCESS.md` (4-step procedure: bump 3 files → tag → GitHub release → PyPI).
- **Active refactoring plan**: see `docs/REFACTORING_PLAN.md` — 10-week / 8-phase plan with hard `100% backwards compatibility` constraint. API changes (e.g. native list params) are explicitly out of scope and live in `docs/V2_API_MIGRATION.md`.

## Important Reminders
- Never hardcode authentication tokens
- Keep root directory clean (use appropriate subdirectories)
- Prefer editing existing files over creating new ones
- Test with actual Things 3 before marking features complete
- When we add new capabilities, we need to always be sure to "advertise them" to the AI using the MCP server