from mcp.server.fastmcp import Context
import json
from rhinomcp.server import get_rhino_connection, mcp, logger
from typing import Any, List, Dict


@mcp.tool()
async def modify_object(
    ctx: Context,
    id: str = None,
    name: str = None,
    new_name: str = None,
    new_color: List[int] = None,
    translation: List[float] = None,
    rotation: List[float] = None,
    scale: List[float] = None,
    visible: bool = None
) -> str:
    """
    Modify an existing object in the Rhino document.
    
    Parameters:
    - id: The id of the object to modify
    - name: The name of the object to modify
    - new_name: Optional new name for the object
    - new_color: Optional [r, g, b] color values (0-255) for the object
    - translation: Optional [x, y, z] translation vector
    - rotation: Optional [x, y, z] rotation in radians
    - scale: Optional [x, y, z] scale factors
    - visible: Optional boolean to set visibility
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection(ctx)
        
        params : Dict[str, Any] = {}
        
        if id is not None:
            params["id"] = id
        if name is not None:
            params["name"] = name
        if new_name is not None:
            params["new_name"] = new_name
        if new_color is not None:
            params["new_color"] = new_color
        if translation is not None:
            params["translation"] = translation
        if rotation is not None:
            params["rotation"] = rotation
        if scale is not None:
            params["scale"] = scale
        if visible is not None:
            params["visible"] = visible
            
        result = await rhino.send_command("modify_object", params)
        return f"Modified object: {result['name']}"
    except Exception as e:
        logger.error(f"Error modifying object: {str(e)}")
        return f"Error modifying object: {str(e)}"