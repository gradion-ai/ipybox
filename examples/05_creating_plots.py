"""
Example demonstrating how to create and save matplotlib plots.
"""

import asyncio

from ipybox import ExecutionClient, ExecutionContainer


async def main():
    # --8<-- [start:usage]
    async with ExecutionContainer() as container:
        async with ExecutionClient(port=container.executor_port) as client:
            execution = await client.submit("""
                !pip install matplotlib

                import matplotlib.pyplot as plt
                import numpy as np

                x = np.linspace(0, 10, 100)
                plt.figure(figsize=(8, 6))
                plt.plot(x, np.sin(x))
                plt.title('Sine Wave')
                plt.show()

                print("Plot generation complete!")
                """)  # (1)!

            async for chunk in execution.stream():  # (2)!
                print(chunk, end="", flush=True)

            result = await execution.result()
            result.images[0].save("sine.png")  # (3)!
    # --8<-- [end:usage]


if __name__ == "__main__":
    asyncio.run(main())
