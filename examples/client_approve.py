import asyncio

from ipybox.kernel.executor import ExecutionClient
from ipybox.kernel.gateway import KernelGateway
from ipybox.mcp.runner.approval import Approval, ApprovalClient
from ipybox.mcp.runner.server import ToolServer

CODE_1 = """
from mcptools.brave_search import brave_web_search as bws

result = bws.run(bws.Params(query="martin krasser", count=3))
print(result)
"""


async def main():
    async def on_approval(approval: Approval):
        print(f"Approval request: {approval}")
        await approval.approve()

    async with KernelGateway():
        async with ToolServer(approval_required=True):
            async with ApprovalClient(callback=on_approval):
                async with ExecutionClient() as client:
                    result = await client.execute(CODE_1)
                    print(result.text)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
