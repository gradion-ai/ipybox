# Code action plugin for Claude Code

This plugin installs ipybox as MCP server in Claude Code together with a code action skill. 
It enables Claude Code to call MCP tools programmatically in code actions executed in ipybox.
Code actions themselves can be saved and reused as tools in other code actions generated later.
Over time, a library of code actions can be built, composed of other code actions and MCP tools.

Code actions and MCP tools are discovered via agentic search
Their sources are inspected on demand to understand their interfaces so that they can be properly used.
This progressive disclosure approach frees Claude Code from pre-loading interfaces into its system prompt.
Only sources that are actually needed are loaded into the agent's context window.

Code actions are stored such that their interface is separated from implementation details.
This enables Claude Code to inspect only the relevant parts of a code action without being distracted by implementation details.
Separating interface from implementation also reduces token consumption when inspecting code actions.

Here's an overview how responsibilities are distributed between ipybox and Claude Code:

ipybox provides:
- generation of Python tool APIs from MCP server tool schemas
- sandboxed execution of Python code that uses the generated APIs
- fully local code execution without any cloud dependencies

The code action skill instructs Claude Code how to:
- augment generated Python tool APIs so that they can be better chained in code actions
- discover and inspect tools and code actions via agentic search on the filesystem
- select tools and code actions appropriate for the task, based on their Python interfaces
- generate and execute code in ipybox that composes MCP tools and saved code actions
- save successful code actions with a structure for efficient discovery and reuse

## Installation

...

## Usage example

...
