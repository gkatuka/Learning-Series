from mcp.server.fastmcp import FastMCP


# Create an MCP server
mcp = FastMCP(
    name="Greeting",
    host="0.0.0.0",  # only used for SSE transport (localhost)
    port=8050,  # only used for SSE transport (set this to any port)
)


# Add a simple calculator tool
@mcp.tool()
async def greeting(name: str) -> str:
    """
    Returns a greeting message.

    Parameters:
    name (str): The name to greet.

    Returns:
    str: A greeting message.
    """
    return f"Hello, {name}! This is a simple MCP server response."

# Run the server
if __name__ == "__main__":
    transport = "stdio"
    if transport == "stdio":
        print("Running server with stdio transport")
        mcp.run(transport="stdio")
    elif transport == "sse":
        print("Running server with SSE transport")
        mcp.run(transport="sse")
    else:
        raise ValueError(f"Unknown transport: {transport}")