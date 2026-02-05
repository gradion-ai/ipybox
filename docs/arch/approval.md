# Code Execution and Approval Architecture

This document describes the architecture and dynamics of code execution with
programmatic MCP tool calls, focusing on approval requests and timeout behavior.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CodeExecutor                                   │
│                                                                             │
│  Orchestrates code execution with MCP tool approval. Owns and manages:     │
│  - KernelGateway/KernelClient (code execution)                             │
│  - ToolServer (MCP tool execution)                                         │
│  - ApprovalClient (receives approval requests)                             │
│                                                                             │
│  Timeout parameters:                                                        │
│  - approval_timeout: passed to ToolServer                                  │
│  - connect_timeout: passed to ToolServer                                   │
│  - timeout: per-call parameter in stream()/execute()                       │
└─────────────────────────────────────────────────────────────────────────────┘
          │                           │                          │
          │ manages                   │ manages                  │ manages
          ▼                           ▼                          ▼
┌───────────────────┐     ┌─────────────────────┐     ┌───────────────────────┐
│   KernelGateway   │     │     ToolServer      │     │    ApprovalClient     │
│                   │     │                     │     │                       │
│ Jupyter Kernel    │     │ HTTP server for MCP │     │ WebSocket client that │
│ Gateway process   │     │ tool execution      │     │ receives approval     │
│                   │     │                     │     │ requests and sends    │
│                   │     │ Endpoints:          │     │ accept/reject         │
│                   │     │ - POST /run         │     │ responses             │
│                   │     │ - WS /approval      │     │                       │
│                   │     │                     │     │ Callback invoked for  │
│                   │     │ Owns:               │     │ each ApprovalRequest  │
│                   │     │ - ApprovalChannel   │     │                       │
│                   │     │ - MCPClient cache   │     │                       │
└─────────────────────────┴─────────────────────┴─────┴───────────────────────┘
          │                           │                          │
          │                           │                          │
          ▼                           ▼                          │
┌───────────────────┐     ┌─────────────────────┐                │
│   KernelClient    │     │  ApprovalChannel    │◄───────────────┘
│                   │     │                     │    WebSocket
│ WebSocket client  │     │ Server-side channel │    connection
│ for IPython       │     │ for approval over   │
│ kernel comm       │     │ WebSocket           │
│                   │     │                     │
│ Applies code      │     │ Applies approval    │
│ execution timeout │     │ timeout             │
│ when used directly│     │                     │
└───────────────────┘     └─────────────────────┘
          │                           │
          │ executes                  │ calls
          ▼                           ▼
┌───────────────────┐     ┌─────────────────────┐
│  IPython Kernel   │     │     MCPClient       │
│                   │     │                     │
│ Python runtime    │     │ Client for MCP      │
│ with state        │     │ servers (stdio,     │
│                   │     │ HTTP, SSE)          │
│ Code calls        │     │                     │
│ ToolRunner for    │     │ Applies connect     │
│ MCP tools         │     │ timeout on startup  │
└───────────────────┘     └─────────────────────┘
          │
          │ HTTP POST /run
          ▼
┌───────────────────┐
│    ToolRunner     │
│                   │
│ Sync HTTP client  │
│ for calling       │
│ ToolServer from   │
│ kernel code       │
│                   │
│ Blocks until      │
│ tool completes    │
└───────────────────┘
```

## Sequence Diagram: Code Execution with Tool Call and Approval

The following diagram shows the execution flow when code running in the IPython
kernel calls an MCP tool that requires approval.

```
┌──────────┐  ┌────────────────┐  ┌──────────────┐  ┌────────────┐  ┌────────────────┐  ┌───────────┐
│   App    │  │  CodeExecutor  │  │ KernelClient │  │ ToolServer │  │ApprovalChannel │  │ MCPClient │
└────┬─────┘  └───────┬────────┘  └──────┬───────┘  └─────┬──────┘  └───────┬────────┘  └─────┬─────┘
     │                │                  │                │                 │                 │
     │  stream(code, timeout=T)          │                │                 │                 │
     │───────────────>│                  │                │                 │                 │
     │                │                  │                │                 │                 │
     │                │  ApprovalClient  │                │                 │                 │
     │                │  connects via WS │                │                 │                 │
     │                │─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─>│                 │                 │
     │                │                  │                │                 │                 │
     │                │  stream(code, timeout=T)          │                 │                 │
     │                │─────────────────>│                │                 │                 │
     │                │                  │                │                 │                 │
     │                │                  │ ╔══════════════════════════════╗ │                 │
     │                │                  │ ║ asyncio.timeout(T) STARTS   ║ │                 │
     │                │                  │ ╚══════════════════════════════╝ │                 │
     │                │                  │                │                 │                 │
     │                │                  │ execute_request│                 │                 │
     │                │                  │───────────────>│                 │                 │
     │                │                  │      IPython Kernel              │                 │
     │                │                  │                │                 │                 │
     │                │                  │     ═══════════════════════════  │                 │
     │                │                  │     Code runs, calls MCP tool    │                 │
     │                │                  │     via ToolRunner.run_sync()    │                 │
     │                │                  │     ═══════════════════════════  │                 │
     │                │                  │                │                 │                 │
     │                │                  │                │ POST /run       │                 │
     │                │                  │                │<────────────────│                 │
     │                │                  │                │  (from kernel)  │                 │
     │                │                  │                │                 │                 │
     │                │                  │                │ request(...)    │                 │
     │                │                  │                │────────────────>│                 │
     │                │                  │                │                 │                 │
     │                │                  │                │ ╔══════════════════════════════╗  │
     │                │                  │                │ ║ asyncio.timeout(A) STARTS   ║  │
     │                │                  │                │ ║ (approval_timeout)          ║  │
     │                │                  │                │ ╚══════════════════════════════╝  │
     │                │                  │                │                 │                 │
     │                │                  │                │  WS: approve    │                 │
     │                │                  │                │  request ───────┼────────────────>│
     │                │                  │                │                 │   ApprovalClient│
     │                │                  │                │                 │                 │
     │                │   ApprovalRequest│                │                 │                 │
     │                │<─ ─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─ │                 │
     │                │   (via queue)    │                │                 │                 │
     │ ApprovalRequest│                  │                │                 │                 │
     │<───────────────│                  │                │                 │                 │
     │                │                  │                │                 │                 │
     │     ═══════════════════════════════════════════════════════════════════════════════════│
     │     App decides whether to accept/reject. This wait time counts against BOTH:         │
     │     - Code execution timeout (T) in KernelClient                                      │
     │     - Approval timeout (A) in ApprovalChannel                                         │
     │     ═══════════════════════════════════════════════════════════════════════════════════│
     │                │                  │                │                 │                 │
     │  accept()      │                  │                │                 │                 │
     │───────────────>│                  │                │                 │                 │
     │                │                  │                │                 │                 │
     │                │  WS: approve     │                │                 │                 │
     │                │  response ───────┼────────────────┼────────────────>│                 │
     │                │                  │                │                 │                 │
     │                │                  │                │ approval: True  │                 │
     │                │                  │                │<────────────────│                 │
     │                │                  │                │                 │                 │
     │                │                  │                │ ╔══════════════════════════════╗  │
     │                │                  │                │ ║ asyncio.timeout(A) ENDS     ║  │
     │                │                  │                │ ╚══════════════════════════════╝  │
     │                │                  │                │                 │                 │
     │                │                  │                │ run(tool, args) │                 │
     │                │                  │                │────────────────────────────────>│
     │                │                  │                │                 │                 │
     │                │                  │                │  tool result    │                 │
     │                │                  │                │<────────────────────────────────│
     │                │                  │                │                 │                 │
     │                │                  │  HTTP response │                 │                 │
     │                │                  │  (tool result) │                 │                 │
     │                │                  │<───────────────│                 │                 │
     │                │                  │  to kernel     │                 │                 │
     │                │                  │                │                 │                 │
     │                │                  │     ═══════════════════════════  │                 │
     │                │                  │     Code continues execution     │                 │
     │                │                  │     ═══════════════════════════  │                 │
     │                │                  │                │                 │                 │
     │                │                  │ execute_reply  │                 │                 │
     │                │                  │<───────────────│                 │                 │
     │                │                  │                │                 │                 │
     │                │                  │ ╔══════════════════════════════╗ │                 │
     │                │                  │ ║ asyncio.timeout(T) ENDS     ║ │                 │
     │                │                  │ ╚══════════════════════════════╝ │                 │
     │                │                  │                │                 │                 │
     │                │ ExecutionResult  │                │                 │                 │
     │                │<─────────────────│                │                 │                 │
     │                │                  │                │                 │                 │
     │CodeExecutionResult               │                │                 │                 │
     │<───────────────│                  │                │                 │                 │
     │                │                  │                │                 │                 │
```

## Timeout Configuration

Three independent timeout mechanisms exist in the system:

### 1. Code Execution Timeout

| Property | Value |
|----------|-------|
| **Parameter** | `timeout` in `CodeExecutor.stream()` / `CodeExecutor.execute()` |
| **Type** | `float | None` |
| **Default** | `None` (no timeout) |
| **Applied in** | `CodeExecutor.stream()` |
| **Mechanism** | Deadline-based budget with pause/resume on approval requests |
| **On expiry** | Kernel is interrupted via `KernelClient.interrupt()`, `asyncio.TimeoutError` raised |

This timeout is enforced in `CodeExecutor` while waiting for kernel output.
Approval wait time is excluded by pausing the budget until a decision is made.
`KernelClient.stream()` still supports its own timeout when used directly, but
`CodeExecutor` always calls it with `timeout=None`.

**Code location** (`code_exec.py`, simplified):

```python
deadline = time.monotonic() + timeout
item = await asyncio.wait_for(queue.get(), timeout=remaining)
item.set_on_decision(lambda: resume_event.set())
```

### 2. Approval Timeout

| Property | Value |
|----------|-------|
| **Parameter** | `approval_timeout` in `CodeExecutor.__init__()` |
| **Type** | `float | None` |
| **Default** | `None` (no timeout) |
| **Passed through** | `CodeExecutor` -> `ToolServer` -> `ApprovalChannel` |
| **Applied in** | `ApprovalChannel.request()` at line 109 |
| **Mechanism** | `asyncio.timeout(self.approval_timeout)` context manager |
| **On expiry** | `TimeoutError` raised, caught by `ToolServer.run()`, returns error response |

This timeout controls how long the system waits for an approval decision
(accept or reject) from the `ApprovalClient`.

**Code location** (`tool_exec/approval/server.py:108-114`):

```python
try:
    async with asyncio.timeout(self.approval_timeout):
        request_id = await self._send_approval_request(server_name, tool_name, tool_args)
        return await self._requests[request_id]
finally:
    if request_id is not None:
        self._requests.pop(request_id, None)
```

### 3. Connect Timeout

| Property | Value |
|----------|-------|
| **Parameter** | `connect_timeout` in `CodeExecutor.__init__()` |
| **Type** | `float` |
| **Default** | `30` seconds |
| **Passed through** | `CodeExecutor` -> `ToolServer` -> `MCPClient` |
| **Applied in** | `MCPClient` during session initialization |
| **Mechanism** | `asyncio.wait_for(session.initialize(), timeout=self.connect_timeout)` |
| **On expiry** | MCP server connection fails |

This timeout applies only when starting/connecting to an MCP server for the
first time. It does not affect tool execution or approval requests.

## The Timeout Nesting Problem

Previously, the critical issue was that **approval wait time counted against
code execution timeout**. The timeouts were not independent - they were nested:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Code Execution Timeout (outer)                          │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    Time consumed by code execution                   │  │
│   │                                                                      │  │
│   │   ┌────────────────────────────────────────────────────────────────┐ │  │
│   │   │              Tool Call (blocking HTTP request)                 │ │  │
│   │   │                                                                │ │  │
│   │   │   ┌──────────────────────────────────────────────────────────┐ │ │  │
│   │   │   │            Approval Timeout (nested)                     │ │ │  │
│   │   │   │                                                          │ │ │  │
│   │   │   │   ┌────────────────────────────────────────────────────┐ │ │ │  │
│   │   │   │   │         Time waiting for user decision             │ │ │ │  │
│   │   │   │   └────────────────────────────────────────────────────┘ │ │ │  │
│   │   │   │                                                          │ │ │  │
│   │   │   └──────────────────────────────────────────────────────────┘ │ │  │
│   │   │                                                                │ │  │
│   │   │   ┌──────────────────────────────────────────────────────────┐ │ │  │
│   │   │   │            MCP tool execution time                       │ │ │  │
│   │   │   └──────────────────────────────────────────────────────────┘ │ │  │
│   │   │                                                                │ │  │
│   │   └────────────────────────────────────────────────────────────────┘ │  │
│   │                                                                      │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Why This Used to Happen (before CodeExecutor budgeting)

1. **KernelClient.stream()** applies `asyncio.timeout(timeout)` around the
   message-reading loop

2. When kernel code calls a tool via `ToolRunner.run_sync()`, it makes a
   **blocking HTTP POST** to the ToolServer

3. The ToolServer's `/run` endpoint calls `ApprovalChannel.request()` which
   sends an approval request and waits for a response

4. While waiting for approval, the HTTP request is blocked, the kernel code is
   blocked, and the `asyncio.timeout(timeout)` in KernelClient continues
   counting down

5. The approval wait time is therefore consumed from the code execution timeout
   budget

### Current Behavior (resolved)

The timeout is now enforced in `CodeExecutor.stream()` using a deadline-based
budget. When an approval request is emitted, the budget is paused until
`accept()` or `reject()` is called. This ensures approval wait time does not
count against the execution timeout while still counting tool runtime and kernel
execution time.

### Previously Problematic Scenarios (now avoided)

**Scenario 1: Approval takes too long**

Configuration:
- `code_timeout = 60` seconds
- `approval_timeout = None` (unlimited)

Timeline:
1. Code starts executing (0s)
2. Code runs for 5 seconds (5s elapsed)
3. Tool call triggers approval request (5s elapsed)
4. User takes 58 seconds to approve (63s elapsed)
5. **With the new behavior**, execution does **not** time out at 60s because the
   58s approval wait is excluded

**Scenario 2: Approval timeout shorter than code timeout, but both expire**

Configuration:
- `code_timeout = 30` seconds
- `approval_timeout = 10` seconds

Timeline:
1. Code starts executing (0s)
2. Code runs for 25 seconds (25s elapsed)
3. Tool call triggers approval request (25s elapsed)
4. Approval timeout expires at 35s total, but code timeout expires at 30s
5. **With the new behavior**, the approval timeout error is returned before any
   execution timeout is raised

### Observing Timeouts Now

When the code execution timeout expires now:

1. `CodeExecutor.stream()` detects the timeout based on remaining budget
2. It calls `KernelClient.interrupt()` to stop the kernel
3. The `TimeoutError` propagates to the caller
4. The application receives `asyncio.TimeoutError`

The error message does not distinguish between:
- Code that ran too long
- Code that was blocked waiting for MCP tool execution

### Key Code Paths

**Code execution timeout applied** (`code_exec.py`):
```python
remaining = deadline - time.monotonic()
item = await asyncio.wait_for(queue.get(), timeout=remaining)
```

**Timeout budget pause/resume** (`code_exec.py`):
```python
item.set_on_decision(lambda: resume_event.set())
```

**Tool call blocks kernel** (`tool_exec/client.py:74-94`):
```python
def run_sync(self, tool_name: str, tool_args: dict[str, Any]):
    response = requests.post(...)  # Synchronous HTTP - blocks kernel
    # ...
```

**Approval request blocks tool server** (`tool_exec/server.py:115-122`):
```python
async def run(self, call: ToolCall):
    try:
        if not await self._approval_channel.request(...):  # Blocks here
            return {"error": "...rejected"}
    except asyncio.TimeoutError:
        return {"error": "...expired"}
```

**Approval timeout applied** (`tool_exec/approval/server.py:108-114`):
```python
async with asyncio.timeout(self.approval_timeout):
    request_id = await self._send_approval_request(...)
    return await self._requests[request_id]  # Blocks waiting for response
```

## Summary

The timeout nesting issue is resolved by enforcing execution timeouts in
`CodeExecutor` and pausing the budget during approval waits. As a result:

1. **Predictable execution budgets**: Approval latency no longer reduces the
   time available for kernel and tool execution

2. **Simpler configuration**: Execution timeouts can be set without accounting
   for user response time

3. **Clearer attribution**: Timeouts now indicate slow kernel execution or slow
   MCP tool execution (not approval latency)
