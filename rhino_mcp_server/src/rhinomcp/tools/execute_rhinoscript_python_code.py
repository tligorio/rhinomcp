from mcp.server.fastmcp import Context
import json
from rhinomcp.server import get_rhino_connection, mcp, logger
from typing import Any, List, Dict


@mcp.tool()
def execute_rhinoscript_python_code(ctx: Context, code: str) -> Dict[str, Any]:
    """
    Execute arbitrary RhinoScript code in Rhino.
    
    Parameters:
    - code: The RhinoScript code to execute

    To get any output from the script, you should use the python `print` function.

    References:

    AddBox(corners)
        Adds a box shaped polysurface to the document
    Parameters:
        corners ([point, point, point ,point, point, point ,point,point]) 8 points that define the corners of the box. Points need to
        be in counter-clockwise order starting with the bottom rectangle of the box
    Returns:
        guid: identifier of the new object on success
    Example:
        import rhinoscriptsyntax as rs
        box = rs.GetBox()
        if box: rs.AddBox(box)

    AddSphere(center_or_plane, radius)
        Add a spherical surface to the document
    Parameters:
        center_or_plane (point|plane): center point of the sphere. If a plane is input,
        the origin of the plane will be the center of the sphere
        radius (number): radius of the sphere in the current model units
    Returns:
        guid: identifier of the new object on success
        None: on error
    Example:
        import rhinoscriptsyntax as rs
        radius = 2
        center = rs.GetPoint("Center of sphere")
        if center: rs.AddSphere(center, radius)


    """
    try:
        # Get the global connection
        rhino = get_rhino_connection()
        
        return rhino.send_command("execute_rhinoscript_python_code", {"code": code})

    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return {"success": False, "message": str(e)}