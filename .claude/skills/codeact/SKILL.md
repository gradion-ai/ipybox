---
name: codeact
description: Generate and execute code for acting with Python tools. Activate when user explicitly requests to "use the codeact skill" or similar phrases.
---

Use Python tools to perform tasks.

You must use the `execute_ipython_cell` tool of the `ipybox` MCP server for executing Python code.

All operations must follow the tool usage restrictions and workflows defined below.

## Tool Directories

The `gentools/` and `mcptools/` directories are in the **working directory** shown in your `<env>` block. All paths are relative to the working directory, NOT to this skill's base directory.

## Tool Usage Restrictions

You are restricted to these tools only:

### Python Tools

- Functions in `mcptools/<category>/<tool>.py` (use `run_parsed` if defined, otherwise `run`)
- Functions in `gentools/<category>/<tool>/api.py`

### `ipybox` MCP Server Tools

- `execute_ipython_cell` - Execute Python code
- `reset` - Reset the IPython kernel

### Claude Code Filesystem Tools

- All filesystem tools for reading, writing files, and listing directories.

## Workflow

### 1. Python Tool Selection

1. List available categories in `gentools/` and `mcptools/`
2. List available tools in relevant categories
3. Read tool files to understand interfaces and parameters.

### 2. Python Tool Priority

1. Search `gentools` package first
2. If not found, search `mcptools` package
3. If no appropriate tool exists, generate custom code

### 3. Code Generation and Python Tool Chaining

- Generate code that uses selected Python tools as argument for `execute_ipython_cell`.
- Chain Python tools in the generated code if the structured output of one tool can be used as input for another tool.

### 4. Code Execution

- Use the `execute_ipython_cell` for Python code execution
- Print only required information, not intermediate results
- Store intermediate results in variables

## Output Parsers

When generating output parsers for Python tools in the `mcptools` package, see [references/output-parsers.md](references/output-parsers.md).

## Saving Code Actions

To save executed code as a reusable gentools tool, see [references/saving-codeacts.md](references/saving-codeacts.md).
