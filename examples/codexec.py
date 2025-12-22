import asyncio
import tempfile
from pathlib import Path

# --8<-- [start:imports]
from ipybox import (
    ApprovalRequest,
    CodeExecutionChunk,
    CodeExecutionResult,
    CodeExecutor,
)

# --8<-- [end:imports]


async def basic_execution():
    # --8<-- [start:basic_execution]
    async with CodeExecutor() as executor:
        result = await executor.execute("print('hello world')")
        assert result.text == "hello world"
    # --8<-- [end:basic_execution]


async def basic_approval():
    # --8<-- [start:basic_approval]
    code = """
    from mcptools.brave_search.brave_image_search import Params, Result, run

    result: Result = run(Params(query="neural topic models", count=3))
    print(f"num results = {len(result.items)}")
    """
    async with CodeExecutor() as executor:
        async for item in executor.stream(code):
            match item:
                case ApprovalRequest():
                    assert item.tool_name == "brave_image_search"
                    assert item.tool_args["query"] == "neural topic models"
                    assert item.tool_args["count"] == 3
                    await item.accept()
                case CodeExecutionResult():
                    assert item.text == "num results = 3"
    # --8<-- [end:basic_approval]


async def basic_chunks():
    # --8<-- [start:basic_chunks]
    code = """
    from time import sleep
    print("chunk 1")
    sleep(0.5)
    print("chunk 2")
    """
    async with CodeExecutor() as executor:
        async for item in executor.stream(code, chunks=True):
            match item:
                case CodeExecutionChunk():
                    assert item.text.strip() in ["chunk 1", "chunk 2"]
                case CodeExecutionResult():
                    assert item.text == "chunk 1\nchunk 2"
    # --8<-- [end:basic_chunks]


async def basic_plotting():
    # --8<-- [start:basic_plotting]
    code = """
    import matplotlib.pyplot as plt
    plt.plot([1, 2, 3], [1, 4, 9])
    plt.show()
    """
    with tempfile.TemporaryDirectory() as images_dir:
        async with CodeExecutor(images_dir=Path(images_dir)) as executor:
            result = await executor.execute(code)
            assert len(result.images) == 1
            assert result.images[0].exists()
            assert result.images[0].suffix == ".png"
    # --8<-- [end:basic_plotting]


async def custom_timeouts():
    # --8<-- [start:custom_timeouts]
    # set custom approval timeout, default is no timeout
    async with CodeExecutor(approval_timeout=10) as executor:
        # set custom execution timeout, default is no timeout
        async for item in executor.stream("...", timeout=10):
            ...
    # --8<-- [end:custom_timeouts]


async def kernel_environment():
    # --8<-- [start:kernel_environment]
    # IPython kernel does not inherit environment variables from parent process
    # Kernel environment must be explicitly set using the kernel_env parameter
    async with CodeExecutor(kernel_env={"TEST_VAR": "test_val"}) as executor:
        result = await executor.execute("import os; print(os.environ['TEST_VAR'])")
        assert result.text == "test_val"
    # --8<-- [end:kernel_environment]


async def kernel_reset():
    # --8<-- [start:kernel_reset]
    async with CodeExecutor() as executor:
        await executor.execute("x = 42")
        result = await executor.execute("print(x)")
        assert result.text == "42"

        await executor.reset()

        code = """
        try:
            print(x)
        except NameError:
            print("x not defined")
        """
        result = await executor.execute(code)
        assert result.text == "x not defined"
    # --8<-- [end:kernel_reset]


async def working_directory():
    # --8<-- [start:working_directory]
    async with CodeExecutor() as executor:
        import os

        result = await executor.execute("import os; print(os.getcwd())")
        assert result.text == os.getcwd()
    # --8<-- [end:working_directory]


async def main():
    await basic_execution()
    await basic_approval()
    await basic_chunks()
    await basic_plotting()
    await custom_timeouts()
    await kernel_environment()
    await kernel_reset()
    await working_directory()


if __name__ == "__main__":
    asyncio.run(main())
