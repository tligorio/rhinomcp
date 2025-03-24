"""Rhino integration through the Model Context Protocol."""

__version__ = "0.1.0"

# Expose key classes and functions for easier imports
from .server import RhinoConnection, get_rhino_connection, mcp, logger

from .prompts.assert_creation_strategy import asset_creation_strategy
from .prompts.assert_query_strategy import assert_query_strategy

from .tools.create_object import create_object
from .tools.create_objects import create_objects
from .tools.delete_object import delete_object
from .tools.get_document_info import get_document_info
from .tools.get_object_info import get_object_info
from .tools.get_selected_objects_info import get_selected_objects_info
from .tools.modify_object import modify_object
from .tools.execute_rhinoscript_python_code import execute_rhinoscript_python_code

