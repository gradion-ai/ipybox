import asyncio
from pathlib import Path

# --8<-- [start:imports]
from ipybox import CodeExecutionError, CodeExecutor, generate_mcp_sources

# --8<-- [end:imports]


async def default_sandbox():
    # --8<-- [start:default_sandbox]
    async with CodeExecutor(sandbox=True) as executor:
        result = await executor.execute("print('hello world')")
        assert result.text == "hello world"

        code = """
        import requests
        try:
            requests.get('https://example.org')
        except Exception as e:
            print(e)
        """

        # Default sandbox config blocks internet access
        result = await executor.execute(code)
        assert "Failed to resolve 'example.org'" in result.text
    # --8<-- [end:default_sandbox]


async def custom_sandbox():
    # --8<-- [start:custom_sandbox]
    code = """
    import requests
    result = requests.get('https://example.org')
    print(result.text)
    """
    async with CodeExecutor(
        sandbox=True,
        sandbox_config=Path("examples/sandbox-kernel.json"),
        log_level="WARNING",
    ) as executor:
        result = await executor.execute(code)
        assert "Example Domain" in result.text
    # --8<-- [end:custom_sandbox]


async def sandboxed_filesystem_mcp_server():
    # --8<-- [start:sandboxed_filesystem_mcp_server_params]
    server_params = {
        "command": "srt",
        "args": [
            "--settings",
            "examples/sandbox-filesystem-mcp.json",
            "npx",
            "-y",
            "@modelcontextprotocol/server-filesystem",
            ".",
        ],
    }
    # --8<-- [end:sandboxed_filesystem_mcp_server_params]

    # --8<-- [start:sandboxed_filesystem_mcp_server_usage]
    await generate_mcp_sources("filesystem", server_params, Path("mcptools"))

    list_dir_code = """
    from mcptools.filesystem.list_directory import run, Params
    result = run(Params(path="."))
    print(result.content)
    """

    read_env_code = """
    from mcptools.filesystem.read_file import run, Params
    result = run(Params(path=".env"))
    print(result.content)
    """

    async with CodeExecutor(sandbox=True) as executor:
        # allowed by MCP server and sandbox
        result = await executor.execute(list_dir_code)
        assert "README.md" in result.text

        try:
            # allowed by MCP server but blocked by sandbox
            result = await executor.execute(read_env_code)
            assert False, "Read access to .env not blocked"
        except CodeExecutionError as e:
            assert "operation not permitted" in str(e)
    # --8<-- [end:sandboxed_filesystem_mcp_server_usage]


async def sandboxed_fetch_mcp_server():
    # --8<-- [start:sandboxed_fetch_mcp_server_params]
    server_params = {
        "command": "srt",
        "args": [
            "--settings",
            "examples/sandbox-fetch-mcp.json",
            "python",
            "-m",
            "mcp_server_fetch",
        ],
    }
    # --8<-- [end:sandboxed_fetch_mcp_server_params]

    # --8<-- [start:sandboxed_fetch_mcp_server_usage]
    await generate_mcp_sources("fetch", server_params, Path("mcptools"))

    fetch_code = """
    from mcptools.fetch import fetch
    result = fetch.run(fetch.Params(url="https://example.com"))
    print(result)
    """

    async with CodeExecutor(sandbox=True) as executor:
        result = await executor.execute(fetch_code)
        print(result.text)
        assert "This domain is for use in documentation examples" in result.text
    # --8<-- [end:sandboxed_fetch_mcp_server_usage]


async def main():
    await default_sandbox()
    await custom_sandbox()
    await sandboxed_filesystem_mcp_server()
    await sandboxed_fetch_mcp_server()


if __name__ == "__main__":
    asyncio.run(main())
