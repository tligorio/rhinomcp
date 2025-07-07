from mcp.server.fastmcp import Context
import json
from rhinomcp.server import get_rhino_connection, mcp, logger
from typing import Any, List, Dict

@mcp.tool()
async def delete_layer(
    ctx: Context,
    guid: str = None,
    name: str = None
) -> str:
    """
    Delete a layer in the Rhino document.
    If name is provided, it will try to delete the layer with the given name.
    If guid is provided, it will try to delete the layer with the given guid.
    If neither is provided, it will return an error.
    
    Parameters:
    - name: The name of the layer to delete.
    - guid: The guid of the layer to delete.
    
    Returns:
    A message indicating the layer was deleted.
    
    Examples of params:
    - name: "Layer 1"
    - guid: "00000000-0000-0000-0000-000000000000"
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection(ctx)

        command_params = {}

        if name is not None:
            command_params["name"] = name
        if guid is not None:
            command_params["guid"] = guid

        # Create the layer
        result = await rhino.send_command("delete_layer", command_params)

        return result["message"]
    except Exception as e:
        logger.error(f"Error deleting layer: {str(e)}")
        return f"Error deleting layer: {str(e)}"
 