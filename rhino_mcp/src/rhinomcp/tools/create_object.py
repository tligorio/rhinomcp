from mcp.server.fastmcp import Context
import json
from rhinomcp.server import get_rhino_connection, mcp, logger
from typing import Any, List, Dict

@mcp.tool()
def create_object(
    ctx: Context,
    type: str = "BOX",
    name: str = None,
    color: List[int]= None,
    params: Dict[str, Any] = {},
    translation: List[float]= None,
    rotation: List[float]= None,
    scale: List[float]= None,
) -> str:
    """
    Create a new object in the Rhino document.
    
    Parameters:
    - type: Object type ("BOX", "SPHERE")
    - name: Optional name for the object
    - color: Optional [r, g, b] color values (0-255) for the object
    - params: Type-specific parameters dictionary (see documentation for each type)
    - translation: Optional [x, y, z] translation vector
    - rotation: Optional [x, y, z] rotation in radians
    - scale: Optional [x, y, z] scale factors

    The params dictionary is type-specific.
    For BOX, the params dictionary should contain the following keys:
    - width: Width of the box along X axis of the object
    - length: Length of the box along Y axis of the object
    - height: Height of the box along Z axis of the object
    
    Returns:
    A message indicating the created object name.
    
    Examples of params:
    - BOX: {"width": 1.0, "length": 1.0, "height": 1.0}
    - SPHERE: {"radius": 1.0}
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection()
        # Set default values for missing parameters
        trans = translation or [0, 0, 0]
        rot = rotation or [0, 0, 0]
        sc = scale or [1, 1, 1]
        
        command_params = {
            "type": type,
            "translation": trans,
            "rotation": rot,
            "scale": sc
        }

        if name: command_params["name"] = name
        if color: command_params["color"] = color

        # Create the object
        result = {}
        if (type == "BOX"):
            command_params["width"] = params["width"]
            command_params["length"] = params["length"]
            command_params["height"] = params["height"]
            result = rhino.send_command("create_object", command_params)
        elif (type == "SPHERE"):
            result = rhino.send_command("create_object", command_params)
        # elif (type == "CYLINDER"):
        #     result = rhino.send_command("create_cylinder", command_params)
            
        
        return f"Created {type} object: {result['name']}"
    except Exception as e:
        logger.error(f"Error creating object: {str(e)}")
        return f"Error creating object: {str(e)}"
 