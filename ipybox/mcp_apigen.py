import asyncio
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types
from datamodel_code_generator.model.base import ALL_MODEL
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser

from ipybox.mcp_client import MCPClient

INIT_TEMPLATE = """
import os
from ipybox.tool_exec.client import ToolRunner

CLIENT = ToolRunner(
    server_name="{server_name}",
    server_params={server_params},
    host=os.environ.get("TOOL_SERVER_HOST", "localhost"),
    port=int(os.environ.get("TOOL_SERVER_PORT", "8900")),
)
"""

FUNCTION_TEMPLATE_UNSTRUCTURED = '''
from . import CLIENT

def run(params: Params) -> str:
    """{description}
    """
    return CLIENT.run_sync(tool_name="{original_name}", tool_args=params.model_dump(exclude_none=True))
'''

FUNCTION_TEMPLATE_STRUCTURED = '''
from . import CLIENT

def run(params: Params) -> Result:
    """{description}
    """
    result = CLIENT.run_sync(tool_name="{original_name}", tool_args=params.model_dump(exclude_none=True))
    return Result.model_validate(result)
'''


def generate_init_definition(server_name: str, server_params: dict[str, Any]):
    return INIT_TEMPLATE.format(server_name=server_name, server_params=server_params)


def indent_description(description: str, indent: str = "    ") -> str:
    """Indent all lines of a description after the first line."""
    lines = description.split("\n")
    if len(lines) <= 1:
        return description
    return lines[0] + "\n" + "\n".join(indent + line if line else line for line in lines[1:])


def generate_function_definition(original_name: str, description: str, structured_output: bool) -> str:
    template = FUNCTION_TEMPLATE_STRUCTURED if structured_output else FUNCTION_TEMPLATE_UNSTRUCTURED
    indented_description = indent_description(description)
    return template.format(
        original_name=original_name,
        description=indented_description.replace('"""', '\\"\\"\\"'),
    )


def generate_input_model_code(schema: dict[str, Any]) -> str:
    return _generate_model_code(schema, "Params")


def generate_output_model_code(schema: dict[str, Any]) -> str:
    return _generate_model_code(schema, "Result")


def _generate_model_code(schema: dict[str, Any], class_name: str) -> str:
    data_model_types = get_data_model_types(
        data_model_type=DataModelType.PydanticV2BaseModel,
        target_python_version=PythonVersion.PY_311,
    )

    extra_template_data = defaultdict(dict)  # type: ignore
    extra_template_data[ALL_MODEL]["config"] = {"use_enum_values": True}

    parser = JsonSchemaParser(
        source=json.dumps(schema),
        class_name=class_name,
        data_model_type=data_model_types.data_model,
        data_model_root_type=data_model_types.root_model,
        data_model_field_type=data_model_types.field_model,
        data_type_manager_type=data_model_types.data_type_manager,
        dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
        use_field_description=True,
        use_double_quotes=True,
        extra_template_data=extra_template_data,
    )
    return parser.parse()


async def generate_mcp_sources(server_name: str, server_params: dict[str, Any], root_dir: Path) -> list[str]:
    """Generate a typed Python tool API for an MCP server.

    Connects to an MCP server, discovers available tools, and generates a Python
    package with typed functions backed by Pydantic models. Each tool becomes a
    module with a `Params` class for input validation and a `run()` function to
    invoke the tool.

    When calling the generated API, the corresponding tools are executed on a
    [`ToolServer`][ipybox.tool_exec.server.ToolServer].

    If a directory for the server already exists under `root_dir`, it is removed
    and recreated.

    Args:
        server_name: Name for the generated package directory. Also used to
            identify the server in the generated client code.
        server_params: MCP server connection parameters. For stdio servers,
            provide `command`, `args`, and optionally `env`. For HTTP servers,
            provide `url` and optionally `headers`.
        root_dir: Parent directory where the package will be created. The
            generated package is written to `root_dir/server_name/`.

    Returns:
        List of sanitized tool names corresponding to the generated module files.

    Example:
        Generate a Python tool API for the fetch MCP server:

        ```python
        server_params = {
            "command": "uvx",
            "args": ["mcp-server-fetch"],
        }
        await generate_mcp_sources("fetch_mcp", server_params, Path("mcptools"))
        ```

        Execute code that uses the generated API:

        ```python
        from ipybox.code_exec import CodeExecutor

        code = \"\"\"
        from mcptools.fetch_mcp import fetch

        result = fetch.run(fetch.Params(url="https://example.com"))
        print(result)
        \"\"\"

        async with CodeExecutor() as executor:
            async for item in executor.execute(code):
                ...
        ```
    """
    async with MCPClient(server_params) as server:
        if await aiofiles.os.path.exists(root_dir / server_name):
            await asyncio.get_running_loop().run_in_executor(None, shutil.rmtree, root_dir / server_name)

        await aiofiles.os.makedirs(root_dir / server_name)

        async with aiofiles.open(root_dir / server_name / "__init__.py", "w") as f:
            await f.write(generate_init_definition(server_name, server_params))

        result = []  # type: ignore

        for tool in await server.list_tools():
            original_name = tool.name
            sanitized_name = sanitize_name(tool.name)
            result.append(sanitized_name)

            # Generate input model (Params)
            input_model_code = generate_input_model_code(tool.inputSchema)

            if output_schema := tool.outputSchema:
                output_model_code = generate_output_model_code(output_schema)
                output_model_code = strip_imports(output_model_code)

            # Generate function with appropriate return type
            function_definition = generate_function_definition(
                original_name=original_name,
                description=tool.description or "",
                structured_output=output_schema is not None,
            )

            # Write file with models and function
            async with aiofiles.open(root_dir / server_name / f"{sanitized_name}.py", "w") as f:
                if output_schema:
                    await f.write(f"{input_model_code}\n\n{output_model_code}\n\n{function_definition}")
                else:
                    await f.write(f"{input_model_code}\n\n{function_definition}")

        return result


def strip_imports(code: str) -> str:
    filtered_lines = []
    for line in code.split("\n"):
        if line.strip() == "from __future__ import annotations":
            continue
        filtered_lines.append(line)
    return "\n".join(filtered_lines)


def sanitize_name(name: str) -> str:
    """Sanitize a name for being used as module name."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
