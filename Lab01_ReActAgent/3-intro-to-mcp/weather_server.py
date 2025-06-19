import asyncio
from typing import Any
import json
import requests 
from mcp.server.fastmcp import FastMCP 

# Initialize FastMCP server
mcp = FastMCP("Weather")

#defining constants
weather_api_base = "https://wttr.in"

# defining the MCP tools using the annotator @mcp.tool()
@mcp.tool()
async def get_weather_info(location: str) -> str:
    """
    Fetches the weather information for the specified location.

    Parameters:
    name (str): The location to fetch weather for.

    Returns:
    str: Weather information as a JSON string.
    """
    
    weather_api_base = "https://wttr.in"
    url = f"{weather_api_base}/{location}?format=j1"
    
    response = requests.get(url)
    
    return str(response.json())

if __name__ == "__main__":
    # initialize and start the MCP server
    mcp.run(transport='stdio')