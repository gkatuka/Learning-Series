import requests
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv("../.env")

# Create an MCP server
mcp = FastMCP(
    name="React with MCP Server",
    host="0.0.0.0",  
    port=8050,  
)

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers together"""
    return a + b

# Add the weather tool
@mcp.tool()
def get_weather(location: str) -> str:
        """
        Fetches the weather information for the specified location.

        :Parameters: The location to fetch weather for.
        :Returns: Weather information as a JSON string.
        """
        weather_api_base = "https://wttr.in"
        url = f"{weather_api_base}/{location}?format=j1"
        
        response = requests.get(url)
        
        return str(response.json())


# Run the server
if __name__ == "__main__":
    transport = "sse"
    if transport == "stdio":
        print("Running server with stdio transport")
        mcp.run(transport="stdio")
    elif transport == "sse":
        print("Running server with SSE transport")
        mcp.run(transport="sse")
    else:
        raise ValueError(f"Unknown transport: {transport}")