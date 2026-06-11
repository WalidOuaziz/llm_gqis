from .project import register_project_tools
from .layers import register_layer_tools
from .processing import register_processing_tools
from .canvas import register_canvas_tools
from .export import register_export_tools
from .system import register_system_tools


def register_all_tools(registry):
    register_project_tools(registry)
    register_layer_tools(registry)
    register_processing_tools(registry)
    register_canvas_tools(registry)
    register_export_tools(registry)
    register_system_tools(registry)
