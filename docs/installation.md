# Installation

## ipybox

Install ipybox using pip:

```bash
pip install ipybox
```

## sandbox-runtime

To use ipybox's sandboxing features, you need to install Anthropic's [sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime) separately. This provides the `srt` command for secure kernel and MCP server isolation.

Install via npm:

```bash
npm install -g @anthropic-ai/sandbox-runtime
```

### Mac OS

On Mac OS, sandbox-runtime requires ripgrep. Install it using Homebrew:

```bash
brew install ripgrep
```

No other dependencies are needed on Mac OS, as sandbox-runtime uses the native `sandbox-exec` command for sandboxing.

### Linux

On Linux, install the required system packages:

```bash
apt-get install bubblewrap socat ripgrep
```

!!! info

    [Sandboxing](sandbox.md) with `srt` currently doesn't work on Linux, but you can still use ipybox with `sandbox=False`.
