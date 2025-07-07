from mcp.server.fastmcp import Context
import json
from rhinomcp.server import get_rhino_connection, mcp, logger
from typing import Any, List, Dict



@mcp.tool()
async def delete_object(ctx: Context, id: str = None, name: str = None, all: bool = None) -> str:
    """
    Delete an object from the Rhino document.
    
    Parameters:
    - id: The id of the object to delete
    - name: The name of the object to delete
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection(ctx)

        commandParams = {}
        if id is not None:
            commandParams["id"] = id
        if name is not None:
            commandParams["name"] = name
        if all:
            commandParams["all"] = all
        
        result = await rhino.send_command("delete_object", commandParams)

        return f"Deleted object: {result['name']}"
    except Exception as e:
        logger.error(f"Error deleting object: {str(e)}")
        return f"Error deleting object: {str(e)}"