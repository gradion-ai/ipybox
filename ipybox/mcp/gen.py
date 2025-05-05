import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os
from datamodel_code_generator import DataModelType, PythonVersion
from datamodel_code_generator.model import get_data_model_types
from datamodel_code_generator.parser.jsonschema import JsonSchemaParser
from mcp import ClientSession

from ipybox.mcp.run import mcp_client

INIT_TEMPLATE = """
SERVER_PARAMS = {server_params}
"""

FUNCTION_TEMPLATE = '''
from ipybox.mcp.run import run_sync
from . import SERVER_PARAMS

def {sanitized_name}(params: Params) -> str:
    """{description}
    """
    return run_sync("{original_name}", params.model_dump(exclude_none=True), SERVER_PARAMS)
'''


def generate_init_definition(server_params: dict[str, Any]):
    return INIT_TEMPLATE.format(server_params=server_params)


def generate_function_definition(sanitized_name: str, original_name: str, description: str):
    return FUNCTION_TEMPLATE.format(
        sanitized_name=sanitized_name,
        original_name=original_name,
        description=description.replace('"""', '\\"\\"\\"'),
    )


def generate_input_definition(schema: dict[str, Any]):
    data_model_types = get_data_model_types(
        data_model_type=DataModelType.PydanticV2BaseModel,
        target_python_version=PythonVersion.PY_311,
    )
    parser = JsonSchemaParser(
        source=json.dumps(schema),
        class_name="Params",
        data_model_type=data_model_types.data_model,
        data_model_root_type=data_model_types.root_model,
        data_model_field_type=data_model_types.field_model,
        data_type_manager_type=data_model_types.data_type_manager,
        dump_resolve_reference_action=data_model_types.dump_resolve_reference_action,
        use_field_description=True,
        use_double_quotes=True,
    )
    return parser.parse()


async def generate_mcp_sources(server_name: str, server_params: dict[str, Any], root_dir: Path) -> list[str]:
    async with mcp_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if await aiofiles.os.path.exists(root_dir / server_name):
                await asyncio.get_running_loop().run_in_executor(None, shutil.rmtree, root_dir / server_name)

            await aiofiles.os.makedirs(root_dir / server_name)

            async with aiofiles.open(root_dir / server_name / "__init__.py", "w") as f:
                await f.write(generate_init_definition(server_params))

            result = []  # type: ignore

            for tool in (await session.list_tools()).tools:
                original_name = tool.name
                sanitized_name = sanitize_name(tool.name)
                result.append(sanitized_name)

                input_definition = generate_input_definition(tool.inputSchema)
                function_definition = generate_function_definition(
                    sanitized_name=sanitized_name,
                    original_name=original_name,
                    description=tool.description,
                )

                async with aiofiles.open(root_dir / server_name / f"{sanitized_name}.py", "w") as f:
                    await f.write(f"{input_definition}\n\n{function_definition}")

            return result


def sanitize_name(name: str) -> str:
    """Sanitize a name for being used as module name."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).lower()
