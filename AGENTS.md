# Repository Guidelines

## Project Structure & Module Organization
- Documentation: `docs/`
- Project description: `docs/index.md`
- Internal documentation:
  - Architecture: `docs/internal/architecture.md`
- Source modules:
  - `ipybox/code_exec.py`: CodeExecutor, main API
  - `ipybox/kernel_mgr/`: KernelGateway and KernelClient
  - `ipybox/tool_exec/`: ToolServer, ToolRunner, approval workflow
  - `ipybox/mcp_apigen.py`: MCP tool wrapper code generation
  - `ipybox/mcp_server.py`: IpyboxMCPServer
  - `ipybox/mcp_client.py`: generic MCP client (stdio, SSE, streamable HTTP)
  - `ipybox/vars.py`: variable replacement utilities
  - `ipybox/utils.py`: shared utilities
- Tests:
  - `tests/unit/`: unit tests
  - `tests/integration/`: integration tests

## Directory-specific Guidelines
- `docs/AGENTS.md`: documentation authoring
- `tests/AGENTS.md`: testing conventions and utilities

## Development Commands

```bash
uv sync                      # Install/sync dependencies
uv add [--dev] [-U] <dep>    # Add a dependency (--dev for dev-only, -U to upgrade)
uv run <command>             # Run <command> in project's venv
uv run invoke cc             # Run code checks (auto-fixes formatting, mypy errors need manual fix)
uv run invoke test           # Run all tests
uv run invoke ut             # Run unit tests only
uv run invoke it             # Run integration tests only
uv run invoke test --cov     # Run tests with coverage
uv run invoke build-docs     # Build docs
uv run invoke serve-docs     # Serve docs at localhost:8000
uv run pytest -xsv tests/integration/test_[name].py             # Single test file
uv run pytest -xsv tests/integration/test_[name].py::test_name  # Single test
```

- `invoke cc` only checks files under version control. Run `git add` on new files first.

## Docstring Guidelines
- Use mkdocs-formatter and mkdocs-docstrings skills for docstrings
- Use Markdown formatting, not reST
- Do not add module-level docstrings

## Coding Guidelines
- All function parameters and return types must have type hints
- Modern union syntax: `str | None` instead of `Optional[str]`
- Prefer `match`/`case` over `isinstance()` for type dispatch

## Commit & Pull Request Guidelines
- Do not include test plan in PR messages
