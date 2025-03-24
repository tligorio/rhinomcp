from rhinomcp.server import mcp


@mcp.prompt()
def asset_creation_strategy() -> str:
    """Defines the preferred strategy for creating assets in Rhino"""
    return """When creating 3D content in Rhino, always start by checking if integrations are available:

    0. Before anything, always check the document from get_document_info()
    1. Please always use the method create_objects() to create multiple objects at once.
    2. When including an object into document, ALWAYS make sure that the name of the object is meanful.
    3. Try to include as many objects as possible accurately and efficiently. If the command is not able to include
       so many data, try to create the objects in batches.
    """
