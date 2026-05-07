# V2 API Migration: Native List Parameters

**Status:** Proposal / not scheduled
**Owner:** TBD
**Target version:** v2.0

This document captures the design rationale and proposed migration path for replacing string-encoded list parameters (e.g. `tags="work,urgent"`) with native JSON arrays (e.g. `tags=["work", "urgent"]`).

This is **distinct from** `REFACTORING_PLAN.md`, which is explicitly internal-only and forbids API changes. The native-list change is by definition a public API change and therefore lives outside that plan.

---

## Motivation

### Current state

Several tool parameters accept comma-separated (or newline-separated) strings instead of native arrays:

| Tool | Parameter | Current type | Separator |
|---|---|---|---|
| `add_todo`, `update_todo` | `tags` | `str` | `,` |
| `add_project`, `update_project` | `tags` | `str` | `,` |
| `add_tags`, `remove_tags` | `tags` | `str` | `,` |
| `bulk_update_todos` | `tags`, `todo_ids` | `str` | `,` |
| `bulk_move_records` | `todo_ids` | `str` | `,` |
| `add_project` | `todos` | `str` | `\n` |

Meanwhile, similar list parameters elsewhere already use native arrays:

| Tool | Parameter | Current type |
|---|---|---|
| `add_todo` | `checklist_items` | `List[str]` |
| `add_checklist_items`, `prepend_checklist_items`, `replace_checklist_items` | `items` | `List[str]` |

So the API is **internally inconsistent**: same conceptual shape ("a list of strings"), two encodings, depending on which tool you call.

### Pain points

1. **Ambiguity for values containing the separator.** `tags="my, tag,work"` is undefined: is that 3 tags or 2? Native arrays make this glass-clear.
2. **LLM has to "encode."** The model must decide: spaces or no spaces? Trailing comma allowed? The CLAUDE.md currently documents this with rules like "no spaces after commas" — this rule only exists because the encoding is string-based.
3. **Validation moves into tool bodies.** With `List[str]`, Pydantic + the JSON schema reject malformed input automatically. With strings, validation is hand-rolled (and bugs have shipped: see `remove_tags()` historic char-array regression).
4. **Schema is less informative.** `{"type": "string", "description": "Comma-separated tags"}` tells the LLM less about the shape than `{"type": "array", "items": {"type": "string"}}`.
5. **Inconsistency degrades tool selection.** LLMs use schema shape as a strong signal; mixing two list encodings for two semantically similar parameters confuses the model.

### Counter-argument (why string encoding exists)

String parameters are nominally easier for hand-typed REPLs / curl-style debugging. In an LLM-driven MCP context, this benefit largely disappears — the consumer is generating JSON anyway.

---

## Who is actually affected by the breaking change?

Smaller blast radius than a typical library breaking change:

| Audience | Impact |
|---|---|
| End users chatting with an AI | None — the AI reads the new schema each session and adapts |
| AI host apps (Claude Desktop, Claude Code, etc.) | None — they pass through tool calls verbatim |
| Direct programmatic callers (rare) | **Affected.** Any script calling `client.call_tool("add_tags", {"tags": "a,b"})` breaks |
| Users with hand-written prompts/contexts that include literal example calls | **Affected.** Their cookbook snippets steer the model toward the old format |
| Project's own docs (CLAUDE.md, README, USER_EXAMPLES.md) | **Affected.** Need synchronized updates |

For most installations the practical impact is "users notice nothing, docs need a sync." This is fundamentally different from breaking a Python library import.

---

## Proposed migration: three phases

### Phase 1 — `v1.5`: Add array params alongside string params (additive, non-breaking)

For every affected tool, accept either form. New canonical name uses the array form; old name is preserved with a deprecation warning.

```python
async def add_tags(
    todo_id: str,
    tags: Optional[str] = Field(
        None,
        description="DEPRECATED: comma-separated tags. Use 'tag_list' instead.",
    ),
    tag_list: Optional[List[str]] = Field(
        None,
        description="Tags to add (preferred form).",
    ),
) -> Dict[str, Any]:
    if tags is not None and tag_list is not None:
        return {"success": False, "error": "Provide either 'tags' or 'tag_list', not both"}
    final_tags = tag_list if tag_list is not None else (
        [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    )
    # ...
```

Same shape applies to `tags` (plain), `todo_ids` (→ `id_list`), and `todos` (→ `todo_titles`).

A deprecation log line should fire whenever the legacy param is used, so server operators can grep for it.

### Phase 2 — `v1.6` to `v1.x`: Migrate docs, examples, and tests

- Update `CLAUDE.md`, `README.md`, `USER_EXAMPLES.md`, `docs/BULK_OPERATIONS_GUIDE.md` to show the new array form everywhere.
- Add a "Deprecated parameters" section to the README listing the soon-to-go names.
- Keep both forms working; emit deprecation warnings.
- Optionally: emit a `tag_warnings` / `migration_warnings` field in tool responses listing legacy params used in the call.

### Phase 3 — `v2.0`: Remove the string params

- Drop the legacy params entirely; only `tag_list`, `id_list`, `todo_titles` remain.
- Rename them back to clean names if desired (`tag_list` → `tags`), now with `List[str]` type.
- CHANGELOG must include a clear migration table.
- Tag and release branch `v1.x` for users who can't migrate immediately; backport critical fixes for ~6 months.

---

## Suggested timeline

| Phase | Earliest | Notes |
|---|---|---|
| v1.5 (dual params) | After REFACTORING_PLAN phases 1-3 land | Don't pile API churn on top of internal refactor |
| v1.6 (docs migration) | 4-8 weeks after v1.5 | Gives early adopters time to find issues |
| v2.0 (cut over) | 6+ months after v1.5 | Long deprecation window because users may not run the server frequently |

Don't start v1.5 while there's open work in `REFACTORING_PLAN.md` — combining internal refactor with API churn makes both reviews harder.

---

## Open questions

- **Final parameter names.** Stay with `tag_list` / `id_list` indefinitely, or rename to clean `tags` / `todo_ids` (with `List[str]` type) in v2.0? Renaming makes for a cleaner end state but requires a second internal migration.
- **Deprecation surfacing.** Log line, structured warning in the response, both, or only docs?
- **Auto-coercion grace period.** In v2.0, should we accept a string and auto-split it as a *temporary* friendliness, or reject hard with a clear error?
- **Other API quirks worth fixing in v2.0** — e.g. boolean-as-string params (`completed: Optional[str]` with values `"true"` / `"false"`) are a sibling smell that might want bundling into the same major bump.

---

## Decision log

- **2026-05-07** — Document created. No implementation scheduled. Surfaced during a code-review pass that flagged the string-encoded list pattern as a degraded LLM-tooling experience but explicitly out of scope for the in-flight refactor plan.
