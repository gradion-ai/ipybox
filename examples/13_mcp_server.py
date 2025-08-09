"""Example demonstrating ipybox as an MCP server.

This example shows how to start and interact with the ipybox MCP server.
"""

import asyncio
import logging

# Configure logging to see server activity
logging.basicConfig(level=logging.INFO)


async def demo_mcp_server_tools():
    """Demonstrate the MCP server tools directly."""
    from ipybox.mcp_server import (
        execute_code,
        install_package,
        list_sessions,
        session_create,
        session_destroy,
        session_status,
        setup_server,
        shutdown_server,
        upload_file,
    )

    print("=== ipybox MCP Server Demo ===\n")

    # Initialize the server
    await setup_server()

    try:
        # 1. List initial sessions (should be empty)
        sessions = await list_sessions()
        print(f"Initial active sessions: {sessions['active_sessions']}")

        # 2. Create a new session
        print("\n1. Creating session...")
        session_info = await session_create(
            session_id="demo-session",
            image="gradion-ai/ipybox",
            timeout_seconds=1800,  # 30 minutes
        )
        print(f"Session created: {session_info}")

        # 3. Execute basic Python code
        print("\n2. Executing basic code...")
        result = await execute_code(
            "demo-session",
            """
print("Hello from ipybox MCP server!")
x = 42
y = x * 2
print(f"x = {x}, y = {y}")
""",
        )
        print(f"Execution result: {result['text_output']}")

        # 4. Test statefulness - variables persist
        print("\n3. Testing statefulness...")
        result = await execute_code(
            "demo-session",
            """
print(f"Previous variables still available: x={x}, y={y}")
z = x + y
print(f"New variable z = {z}")
""",
        )
        print(f"Stateful execution: {result['text_output']}")

        # 5. Create and manipulate data
        print("\n4. Data manipulation...")
        result = await execute_code(
            "demo-session",
            """
import pandas as pd
import numpy as np

# Create sample data
data = pd.DataFrame({
    'A': np.random.randn(5),
    'B': np.random.randn(5),
    'C': np.random.randn(5)
})

print("Sample DataFrame:")
print(data)
print(f"\\nDataFrame shape: {data.shape}")
print(f"Mean values:\\n{data.mean()}")
""",
        )
        print("Data manipulation output:")
        print(result["text_output"])

        # 6. Upload a file
        print("\n5. File operations...")
        file_content = """# Sample Python script
def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("ipybox MCP server"))
"""
        upload_result = await upload_file("demo-session", "sample.py", file_content)
        print(f"File upload result: {upload_result}")

        # Execute the uploaded file
        result = await execute_code(
            "demo-session",
            """
exec(open('sample.py').read())
""",
        )
        print(f"Executed uploaded file: {result['text_output']}")

        # 7. Install and use a package
        print("\n6. Package installation...")
        install_result = await install_package("demo-session", "requests")
        if install_result["status"] == "success":
            print("Package installed successfully")

            # Try using the package
            result = await execute_code(
                "demo-session",
                """
import requests
print("requests library available")
print(f"requests version: {requests.__version__}")
""",
            )
            print(f"Package usage: {result['text_output']}")
        else:
            print(f"Package installation failed: {install_result.get('error_output', 'Unknown error')}")

        # 8. Generate a plot (if matplotlib works)
        print("\n7. Plotting...")
        result = await execute_code(
            "demo-session",
            """
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    import numpy as np

    # Create a simple plot
    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    plt.figure(figsize=(10, 6))
    plt.plot(x, y, 'b-', linewidth=2)
    plt.title('Sine Wave')
    plt.xlabel('x')
    plt.ylabel('sin(x)')
    plt.grid(True)
    plt.savefig('sine_wave.png', dpi=150, bbox_inches='tight')
    plt.close()

    print("Plot saved as sine_wave.png")
    print(f"Plot contains {len(y)} data points")

except ImportError as e:
    print(f"Plotting libraries not available: {e}")
except Exception as e:
    print(f"Error creating plot: {e}")
""",
        )
        print(f"Plotting result: {result['text_output']}")
        if result["images"]:
            print(f"Generated {len(result['images'])} image(s)")

        # 9. Check session status
        print("\n8. Session status...")
        status = await session_status("demo-session")
        print(f"Session uptime: {status['uptime_seconds']:.1f} seconds")
        print(f"Session status: {status['status']}")

        # 10. List sessions
        sessions = await list_sessions()
        print(f"\nActive sessions: {sessions['active_sessions']}")
        for session in sessions["sessions"]:
            print(f"  - {session['session_id']}: uptime {session['uptime']:.1f}s")

    finally:
        # Cleanup
        print("\n9. Cleaning up...")
        await session_destroy("demo-session")
        print("Session destroyed")

        # Verify cleanup
        sessions = await list_sessions()
        print(f"Final active sessions: {sessions['active_sessions']}")

        # Shutdown server
        await shutdown_server()
        print("Server shutdown complete")


async def demo_mcp_server_startup():
    """Demonstrate starting the MCP server."""
    print("\n=== Starting MCP Server ===")
    print("To start the ipybox MCP server, run:")
    print("  python -m ipybox mcp-server --host 0.0.0.0 --port 8080")
    print()
    print("The server will be available at http://localhost:8080")
    print("MCP clients can connect using streamable HTTP transport")
    print()
    print("Example MCP client configuration:")
    print("{")
    print('  "transport": {')
    print('    "type": "sse",')
    print('    "url": "http://localhost:8080/sse"')
    print("  }")
    print("}")


if __name__ == "__main__":
    print("Running ipybox MCP server demonstration...")

    # Show server startup info
    asyncio.run(demo_mcp_server_startup())

    # Run the tools demo
    asyncio.run(demo_mcp_server_tools())
