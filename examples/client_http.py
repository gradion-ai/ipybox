import asyncio
from pathlib import Path

from ipybox.code_exec.client import KernelClient
from ipybox.code_exec.server import KernelGateway

CODE = """
import urllib.request
response = urllib.request.urlopen('https://httpbin.org/get')
content = response.read().decode('utf-8')
print(content)
"""


async def main():
    async with KernelGateway(
        sandbox=True,
        sandbox_config=Path("tests/integration/sandbox.json"),
    ):
        async with KernelClient() as client:
            result = await client.execute(CODE)
            print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
