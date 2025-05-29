import argparse
import io
import mimetypes
import tarfile
from pathlib import Path
from typing import Annotated, Any, Dict, List

import aiofiles
import aiofiles.os
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

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

        # File operations
        self.app.post("/files/{relpath:path}")(self.upload_file)
        self.app.get("/files/{relpath:path}")(self.download_file)
        self.app.delete("/files/{relpath:path}")(self.delete_file)

        # Directory operations
        self.app.post("/directories/{relpath:path}")(self.upload_directory)
        self.app.get("/directories/{relpath:path}")(self.download_directory)

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

    async def upload_file(self, relpath: Path, request: Request):
        """Upload a file to the container."""
        full_path = self._validate_path(relpath)

        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Read file content from request body
        content = await request.body()

        # Write file
        async with aiofiles.open(full_path, mode="wb") as f:
            await f.write(content)

        return {"message": f"File uploaded to {relpath}"}

    async def download_file(self, relpath: Path):
        """Download a file from the container."""
        full_path = self._validate_path(relpath)

        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(full_path))
        if mime_type is None:
            mime_type = "application/octet-stream"

        # Stream file content
        async def file_streamer():
            async with aiofiles.open(full_path, mode="rb") as f:
                while chunk := await f.read(1024 * 1024):  # 1MB chunks
                    yield chunk

        return StreamingResponse(
            file_streamer(),
            media_type=mime_type,
            headers={"Content-Disposition": f"attachment; filename={full_path.name}"},
        )

    async def delete_file(self, relpath: Path):
        """Delete a file from the container."""
        full_path = self._validate_path(relpath)

        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        await aiofiles.os.remove(full_path)
        return Response(status_code=204)

    async def upload_directory(self, relpath: Path, request: Request):
        """Upload a directory as a tar archive."""
        full_path = self._validate_path(relpath)

        # Create target directory
        full_path.mkdir(parents=True, exist_ok=True)

        # Read tar content from request
        content = await request.body()

        # Extract tar archive
        with io.BytesIO(content) as tar_buffer:
            with tarfile.open(fileobj=tar_buffer, mode="r:gz") as tar:
                # Validate all paths before extraction
                for member in tar.getmembers():
                    # Ensure no path escapes the target directory
                    member_path = (full_path / member.name).resolve()
                    try:
                        member_path.relative_to(full_path.resolve())
                    except ValueError:
                        raise HTTPException(status_code=400, detail=f"Invalid tar member: {member.name}")

                # Extract all files
                tar.extractall(path=full_path)

        return {"message": f"Directory uploaded to {relpath}"}

    async def download_directory(self, relpath: Path):
        """Download a directory as a tar archive."""
        full_path = self._validate_path(relpath)

        if not full_path.exists() or not full_path.is_dir():
            raise HTTPException(status_code=404, detail="Directory not found")

        # Create tar archive in memory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            # Add directory contents to archive
            for item in full_path.rglob("*"):
                if item.is_file():
                    # Calculate relative path for archive
                    arcname = item.relative_to(full_path)
                    tar.add(item, arcname=str(arcname))

        # Reset buffer position
        tar_buffer.seek(0)

        return StreamingResponse(
            tar_buffer,
            media_type="application/x-gzip",
            headers={"Content-Disposition": f"attachment; filename={full_path.name}.tar.gz"},
        )

    def _validate_path(self, relpath: Path) -> Path:
        """Validate and resolve path relative to root_dir."""
        # Ensure the path doesn't escape root_dir
        full_path = (self.root_dir / relpath).resolve()
        try:
            full_path.relative_to(self.root_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid path: escapes root directory")
        return full_path

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
