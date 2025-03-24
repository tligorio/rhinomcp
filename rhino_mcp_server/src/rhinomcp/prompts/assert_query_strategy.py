from rhinomcp.server import mcp


@mcp.prompt()
def assert_query_strategy() -> str:
    """Defines the preferred strategy for querying Object or Objects in Rhino"""
    return """When querying Object or Objects in Rhino:
    - if the id of the object is known, use the id to query the object.
    - if the id is not known, use the name of the object to query the object.
    """
