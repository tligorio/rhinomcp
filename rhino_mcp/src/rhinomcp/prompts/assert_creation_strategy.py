from rhinomcp.server import mcp


@mcp.prompt()
def asset_creation_strategy() -> str:
    """Defines the preferred strategy for creating assets in Rhino"""
    return """When creating 3D content in Rhino, always start by checking if integrations are available:

    0. Before anything, always check the document from get_document_info()
    1. Please ALWAYS try to create the objects using the tool execute_rhinoscript_python_code() first.
    2. If there are multiple objects, use the method create_objects() to create multiple objects at once. Do not attempt to create them one by one if they are more than 10.
    3. When including an object into document, ALWAYS make sure that the name of the object is meanful.
    4. Try to include as many objects as possible accurately and efficiently. If the command is not able to include
       so many data, try to create the objects in batches.

    When creating rhinoscript python code:
    - do not hallucinate, only use the syntax that is supported by rhinoscriptsyntax or Rhino,Geometry.
    - document the code that you are writing.
    - when creating objects, ALWAYS make sure that the name of the object is meanful.
    - double check the code if any of the code is not correct, and fix it.
    """
