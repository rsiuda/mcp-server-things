"""Regression tests for MCP tool annotations.

Every tool must declare title + readOnlyHint + destructiveHint to satisfy
Anthropic Directory submission requirements and let MCP clients distinguish
read vs. write operations in their UI.
"""

import pytest

from things_mcp.server import ThingsMCPServer


EXPECTED_TOOL_COUNT = 37
EXPECTED_READ_ONLY_COUNT = 23  # 18 reads + 5 admin/diagnostic
EXPECTED_DESTRUCTIVE_COUNT = 6  # update_*, replace_*, remove_tags, delete_todo

DESTRUCTIVE_TOOLS = {
    "update_todo",
    "update_project",
    "bulk_update_todos",
    "replace_checklist_items",
    "remove_tags",
    "delete_todo",
}


@pytest.fixture
async def registered_tools():
    server = ThingsMCPServer()
    return await server.mcp.list_tools()


class TestToolAnnotations:
    async def test_total_tool_count(self, registered_tools):
        assert len(registered_tools) == EXPECTED_TOOL_COUNT

    async def test_every_tool_has_annotations(self, registered_tools):
        missing = [t.name for t in registered_tools if t.annotations is None]
        assert not missing, f"Tools missing annotations: {missing}"

    async def test_every_tool_has_title(self, registered_tools):
        missing = [
            t.name for t in registered_tools
            if not (t.annotations and t.annotations.title)
        ]
        assert not missing, f"Tools missing title: {missing}"

    async def test_every_tool_declares_read_only_hint(self, registered_tools):
        missing = [
            t.name for t in registered_tools
            if t.annotations.readOnlyHint is None
        ]
        assert not missing, f"Tools missing readOnlyHint: {missing}"

    async def test_every_tool_declares_destructive_hint(self, registered_tools):
        missing = [
            t.name for t in registered_tools
            if t.annotations.destructiveHint is None
        ]
        assert not missing, f"Tools missing destructiveHint: {missing}"

    async def test_read_only_count_matches_plan(self, registered_tools):
        read_only = [t.name for t in registered_tools if t.annotations.readOnlyHint]
        assert len(read_only) == EXPECTED_READ_ONLY_COUNT, (
            f"Expected {EXPECTED_READ_ONLY_COUNT} read-only tools, got {len(read_only)}: {read_only}"
        )

    async def test_destructive_tools_match_plan(self, registered_tools):
        destructive = {t.name for t in registered_tools if t.annotations.destructiveHint}
        assert destructive == DESTRUCTIVE_TOOLS, (
            f"Destructive set drift. Expected: {DESTRUCTIVE_TOOLS}, got: {destructive}"
        )

    async def test_read_only_and_destructive_are_mutually_exclusive(self, registered_tools):
        conflicts = [
            t.name for t in registered_tools
            if t.annotations.readOnlyHint and t.annotations.destructiveHint
        ]
        assert not conflicts, f"Tools marked both read-only and destructive: {conflicts}"
