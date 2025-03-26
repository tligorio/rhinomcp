import mcp.types as types
from rhinomcp.server import mcp
from pydantic import FileUrl


import os
from pathlib import Path

# Define path to static folder
STATIC_FOLDER = Path("./static")


@mcp.list_resource()
async def list_rhinoscriptsyntax_resources() -> list[types.Resource]:
    STATIC_RESOURCES = {}
    for file_path in STATIC_FOLDER.glob("*.py"):
        if file_path.name != "__init__.py":  # Skip __init__.py if present
            key = file_path.stem  # Get filename without extension
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    STATIC_RESOURCES[key] = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
    return [
        types.Resource(
            uri=FileUrl(f"file://{name}.py"),
            name=name,
            description=f"RhinoScriptsyntax for {name}",
            mimeType="text/plain",
        )
        for name in STATIC_RESOURCES.keys()
    ]


@mcp.read_resource()
def get_rhinoscriptsyntax_resource(category: str) -> str:
    """
    RhinoScriptsyntax for a specific category.

    - category: The category of the RhinoScriptsyntax to get.

    following categories are available:
    - application
    - block
    - compat
    - curve
    - dimension
    - document
    - geometry
    - grips
    - group
    - hatch
    - layer
    - light
    - line
    - linetype
    - material
    - mesh
    - object
    - plane
    - pointvector
    - selection
    - surface
    - toolbar
    - transformation
    - userdata
    - userinterface
    - utility
    - view
    """

    for file_path in STATIC_FOLDER.glob("*.py"):
        if file_path.name == f"{category}.py":
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

                
