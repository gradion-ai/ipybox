# Installation

## Python package

Install ipybox using `pip`:

```bash
pip install ipybox
```

or `uv`:

```bash
uv add ipybox
```

## MCP server

ipybox can also be run as an [MCP server](https://gradion-ai.github.io/ipybox/mcpserver/index.md) using `uvx`:

```bash
uvx ipybox --workspace /path/to/workspace
```

See the [MCP server documentation](https://gradion-ai.github.io/ipybox/mcpserver/index.md) for configuration details.

## sandbox-runtime

To use ipybox's [sandboxing](https://gradion-ai.github.io/ipybox/sandbox/index.md) features, you need to install Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) separately. This provides the `srt` command for IPython kernel and MCP server isolation.

Install via npm:

```bash
npm install -g @anthropic-ai/sandbox-runtime@0.0.21
```

### Mac OS

On Mac OS, `sandbox-runtime` requires `ripgrep`. Install it using Homebrew:

```bash
brew install ripgrep
```

No other dependencies are needed on Mac OS, as `sandbox-runtime` uses the native `sandbox-exec` command for sandboxing.

### Linux

On Linux, install the required system packages:

```bash
apt-get install bubblewrap socat ripgrep
```

Info

[Sandboxing](https://gradion-ai.github.io/ipybox/sandbox/index.md) with `srt` currently doesn't work with ipybox on Linux, a fix is work in progress. You can still use ipybox on Linux with `sandbox=False`, or run the ipybox [MCP server](https://gradion-ai.github.io/ipybox/mcpserver/index.md) as a Docker container.
