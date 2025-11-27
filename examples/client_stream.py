import asyncio

from ipybox.code_exec.client import KernelClient
from ipybox.code_exec.server import KernelGateway
from ipybox.tool_exec.approval.client import ApprovalClient, ApprovalRequest
from ipybox.tool_exec.server import ToolServer

CODE_1 = """
from time import sleep
from mcptools.test import tool_2

print("Starting...")
sleep(1)
result = tool_2.run(tool_2.Params(s="hello", delay=1))
print(result)
sleep(1)
print("Done")

"""


async def main():
    async def on_approval(approval: ApprovalRequest):
        print(f"Approval request: {approval}")
        await approval.approve()

    async with KernelGateway():
        async with ToolServer(approval_required=True):
            async with ApprovalClient(callback=on_approval):
                async with KernelClient() as client:
                    result = await client.submit(CODE_1)
                    async for chunk in result.stream():
                        print(chunk, end="", flush=True)
                    print()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    asyncio.run(main())
