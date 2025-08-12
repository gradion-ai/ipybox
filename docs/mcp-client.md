`ipybox` supports the invocation of [MCP](https://modelcontextprotocol.io/) servers in containers via generated MCP client code. An application first calls [`generate_mcp_sources`][ipybox.resource.client.ResourceClient.generate_mcp_sources] to generate a Python function for each tool provided by an MCP server, using the tool's input schema. This needs to be done only once per MCP server. Generated functions are then available on the container's Python path.

!!! example "Generated function"

    The example below generates a [`fetch`](https://github.com/gradion-ai/ipybox/blob/main/docs/mcpgen/fetchurl/fetch.py) function from the input schema of the `fetch` tool provided by the [Fetch MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch).

```python
--8<-- "examples/10_mcp_support.py:import"
--8<-- "examples/10_mcp_support.py:usage"
```

1. Configuration of the [Fetch MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch).
2. Generate MCP client code from an MCP server config. One MCP client function is generated per MCP tool.
3. List of tool names provided by the MCP server. A single `fetch` tool in this example.
4. Execute code that imports and calls the generated MCP client function.
5. Prints
````
```
                         ___                    _
   ____ __________ _____/ (_)___  ____   ____ _(_)
  / __ `/ ___/ __ `/ __  / / __ \/ __ \ / __ `/ /
 / /_/ / /  / /_/ / /_/ / / /_/ / / / // /_/ / /
 \__, /_/   \__,_/\__,_/_/\____/_/ /_(_)__,_/_/
/____/
```
````

Calling a generated MCP client function, executes the corresponding MCP tool. Tools of `stdio` based MCP servers are always executed **inside** the container, while `streamable-http` or legacy `sse` based MCP servers are expected to run elsewhere. Generated MCP client code can be downloaded from the container with [`get_mcp_sources`][ipybox.resource.client.ResourceClient.get_mcp_sources] (not shown).

!!! example "Application example"

    [`freeact`](https://gradion-ai.github.io/freeact/) agents use the `ipybox` MCP integration for [calling MCP tools](https://gradion-ai.github.io/freeact/mcp-integration/) in their code actions.

### Remote MCP servers

In addition to `stdio` based MCP servers that run inside the container, `ipybox` also supports connecting to remote MCP servers running with `streamable-http` or legacy `sse` transports.
This is demonstrated below with an [example MCP server](https://github.com/gradion-ai/ipybox/blob/main/tests/mcp_server.py) that is part of the project. Start the server in a separate terminal on the host machine:

```bash
python tests/mcp_server.py --transport streamable-http --port 8000
```

Then connect to it from your Python script:

```python
--8<-- "examples/10b_mcp_streamable_http.py:import"

--8<-- "examples/10b_mcp_streamable_http.py:usage"
```

1. Configuration of the test MCP server running on the host machine. Replace `[YOUR-HOST-IP-ADDRESS]` with your host machine's IP address.
2. Generate MCP client code from an MCP server config. One MCP client function is generated per MCP tool.
3. List of tool names provided by the test server: `tool_1` and `tool_2`
4. Execute code that imports and calls the generated `tool_1` function
5. Prints: `You passed to tool 1: Hello from ipybox!`
