# Release Process

How to ship a new version. Run all four steps in order; each one assumes the previous succeeded.

## 1. Update version numbers

Three files must agree:

| File | What to change |
|---|---|
| `pyproject.toml` (line ~7) | `version = "X.Y.Z"` |
| `src/things_mcp/__init__.py` (line 3) | `__version__ = "X.Y.Z"` |
| `CHANGELOG.md` (top) | Add `## [X.Y.Z] - YYYY-MM-DD` block with Fixed / Added / Changed sections |

`server.py` imports `__version__` and surfaces it via `get_server_capabilities()`, so once the two source-of-truth files agree, the runtime is automatically correct. No need to touch README/CONTRIBUTING examples — those are placeholders.

## 2. Test, commit, tag, push

```bash
pytest
git add pyproject.toml src/things_mcp/__init__.py CHANGELOG.md
git commit -m "Release vX.Y.Z - Brief description"
git push origin main
git tag vX.Y.Z
git push origin vX.Y.Z
```

## 3. Create the GitHub release

```bash
gh release create vX.Y.Z \
  --title "vX.Y.Z - Release Title" \
  --notes "$(sed -n '/## \[X.Y.Z\]/,/## \[/p' CHANGELOG.md | head -n -1)"
```

The `sed` extracts that version's CHANGELOG block as release notes.

## 4. Publish to PyPI

```bash
python -m build
python -m twine upload dist/mcp_server_things-X.Y.Z*
```

## Checklist

- [ ] `pytest` green
- [ ] Version updated in `pyproject.toml`
- [ ] Version updated in `src/things_mcp/__init__.py`
- [ ] `CHANGELOG.md` updated with date + changes
- [ ] Committed and pushed
- [ ] Tag created and pushed
- [ ] GitHub release created
- [ ] PyPI upload succeeded
- [ ] In a test session, asking Claude "what version is the server" returns X.Y.Z
