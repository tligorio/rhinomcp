from mcp.server.fastmcp import Context
import json
from rhinomcp.server import get_rhino_connection, mcp, logger
from typing import Any, List, Dict


@mcp.tool()
def execute_rhinoscript_python_code(ctx: Context, code: str) -> str:
    """
    Execute arbitrary RhinoScript code in Rhino.

    This function has the highest priority when creating objects, unless the user asks for other methods or this function fails.
    
    Parameters:
    - code: The RhinoScript code to execute
    """
    try:
        # Get the global connection
        rhino = get_rhino_connection()
        
        result = rhino.send_command("execute_rhinoscript_python_code", {"code": code})
        return f"Code executed successfully: {result.get('result', '')}"
    except Exception as e:
        logger.error(f"Error executing code: {str(e)}")
        return f"Error executing code: {str(e)}"