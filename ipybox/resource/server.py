import argparse
from pathlib import Path
from typing import Annotated, Any, Dict, List

import aiofiles
import uvicorn
from fastapi import FastAPI, HTTPException, Query

from ipybox.mcp import gen
from ipybox.modinfo import get_module_info


class ResourceServer:
    def __init__(self, root_dir: Path, host="0.0.0.0", port: int = 8900):
        self.root_dir = root_dir
        self.host = host
        self.port = port

        self.app = FastAPI(title="Resource Server")
        self.app.put("/mcp/{relpath:path}/{server_name}")(self.generate_mcp_sources)
        self.app.get("/mcp/{relpath:path}")(self.get_mcp_sources)
        self.app.get("/modules")(self.get_module_sources)
        self.app.get("/status/")(self.status)

    async def generate_mcp_sources(self, relpath: Path, server_name: str, server_params: Dict[str, Any]):
        return await gen.generate_mcp_sources(server_name, server_params, self.root_dir / relpath)

    async def get_mcp_sources(self, relpath: Path, server_name: str):
        server_dir = self.root_dir / relpath / server_name

        if not server_dir.exists():
            raise HTTPException(status_code=404, detail=f"MCP server {server_name} not found")

        result = {}  # type: ignore
        for file in server_dir.glob("*.py"):
            tool_name = file.stem
            if tool_name != "__init__":
                async with aiofiles.open(file, mode="r") as f:
                    result[tool_name] = await f.read()

        return result

    async def get_module_sources(self, module_names: Annotated[List[str], Query(alias="q")]):
        result = {}

        for module_name in module_names:
            try:
                info = get_module_info(module_name)
                result[info.name] = info.source
            except Exception:
                raise HTTPException(status_code=404, detail=f"Module {module_name} not found")

        return result

    async def status(self):
        return {"status": "ok"}

    def run(self):
        uvicorn.run(self.app, host=self.host, port=self.port)


def main(args):
    server = ResourceServer(root_dir=Path(args.root_dir), host=args.host, port=args.port)
    server.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root-dir", type=Path, default=Path("/app"))
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8900)
    main(parser.parse_args())
