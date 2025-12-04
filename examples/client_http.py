import asyncio
from pathlib import Path

from ipybox.kernel_mgr.client import KernelClient
from ipybox.kernel_mgr.server import KernelGateway

CODE = """
import urllib.request
response = urllib.request.urlopen('https://example.org')
content = response.read().decode('utf-8')
print(content)
"""


async def main():
    async with KernelGateway(
        sandbox=True,
        sandbox_config=Path("tests/integration/sandbox.json"),
    ):
        async with KernelClient() as client:
            result = await client.stream(CODE)
            print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
