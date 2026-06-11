import re
from qgis.PyQt.QtCore import QCoreApplication


TOOL_KEYWORDS = {
    "create_project": ["new", "nouveau", "créer", "create", "blank", "projet"],
    "open_project": ["ouvrir", "open", "load", "charger", "projet", ".qgs", ".qgz"],
    "save_project": ["sauvegarder", "save", "enregistrer"],
    "get_project_info": ["info", "information", "état", "status"],
    "add_layer": ["charge", "load", "add", "ajoute", "shapefile", ".shp", ".gpkg", ".geojson"],
    "add_raster_layer": ["charge", "load", "raster", ".tif", ".asc", "dem"],
    "remove_layer": ["supprime", "remove", "delete", "enlève"],
    "rename_layer": ["renomme", "rename"],
    "list_layers": ["liste", "list", "couche", "layer"],
    "get_layer_info": ["info", "détail", "detail", "propriété"],
    "select_by_expression": ["sélectionne", "select", "filtre", "expression", "where"],
    "clear_selection": ["clear", "désélectionne", "deselect"],
    "add_field": ["ajoute", "add", "champ", "field", "colonne"],
    "calculate_field": ["calcule", "calculate", "surface", "area", "$area", "$length", "$perimeter", "compte", "count", "somme"],
    "group_layers": ["groupe", "group"],
    "create_vector_layer": ["crée", "create", "nouvelle couche", "mémoire", "memory", "vector"],
    "create_raster_layer": ["crée", "create", "nouveau raster", "mémoire", "memory"],
    "run_algorithm": ["buffer", "tampon", "intersect", "union", "dissolve", "merge", "clip", "algorithme", "processing"],
    "list_algorithms": ["liste", "algorithme", "algorithm"],
    "search_algorithms": ["cherche", "search", "trouve"],
    "export_layer": ["exporte", "export", "sauve", "geojson", ".geojson", ".gpkg", ".shp"],
    "import_layer": ["importe", "import"],
    "zoom_to_layer": ["zoom", "centrer", "focus"],
    "zoom_to_extent": ["zoom", "étendue", "extent", "coordonnée"],
    "set_crs": ["crs", "projection", "epsg", "reprojette"],
    "refresh_canvas": ["rafraîchis", "refresh", "update"],
    "list_directory": ["liste", "list", "fichier", "file", "scan", "répertoire", "dossier", "trouve", "cherche"],
    "run_command": ["exécute", "execute", "run", "commande", "command", "terminal", "shell", "cmd", "powershell"],
}

SIGNATURES = {
    "create_project": {
        "type": "direct",
        "purpose": "Create a NEW blank QGIS project",
        "when": "Only when user says 'new project', 'create', 'nouveau projet'. NEVER for open/load.",
        "params": {
            "title": "string, optional, default='Untitled Project'"
        }
    },
    "open_project": {
        "type": "direct",
        "purpose": "OPEN an existing QGIS project file",
        "when": "When user says 'open', 'ouvrir', 'load', 'charger'",
        "params": {
            "path": "string, required, full file path (.qgs or .qgz)"
        }
    },
    "save_project": {
        "type": "direct",
        "purpose": "SAVE the current project to disk",
        "params": {
            "path": "string, optional, save location"
        }
    },
    "get_project_info": {
        "type": "direct",
        "purpose": "Get list of layers and project metadata",
        "params": {}
    },
    "add_layer": {
        "type": "direct",
        "purpose": "LOAD a vector layer from file into the project",
        "params": {
            "path": "string, required, file path (.shp, .gpkg, .geojson)",
            "name": "string, optional, display name (default: filename)"
        }
    },
    "add_raster_layer": {
        "type": "direct",
        "purpose": "LOAD a raster layer from file into the project",
        "params": {
            "path": "string, required, file path (.tif, .asc)",
            "name": "string, optional, display name"
        }
    },
    "remove_layer": {
        "type": "direct",
        "purpose": "REMOVE a layer from the project",
        "params": {"layer": "string, required, layer name or ID"}
    },
    "rename_layer": {
        "type": "direct",
        "purpose": "RENAME a layer",
        "params": {"layer": "string, required", "new_name": "string, required"}
    },
    "list_layers": {
        "type": "direct",
        "purpose": "LIST all layers in the current project",
        "params": {}
    },
    "get_layer_info": {
        "type": "direct",
        "purpose": "Get detailed info about a layer",
        "params": {"layer": "string, required"}
    },
    "select_by_expression": {
        "type": "direct",
        "purpose": "SELECT features matching a QGIS expression",
        "params": {
            "layer": "string, required",
            "expression": "string, required, QGIS expression like \"field\" = 'value'"
        }
    },
    "clear_selection": {
        "type": "direct",
        "purpose": "CLEAR selection on a layer",
        "params": {"layer": "string, required"}
    },
    "add_field": {
        "type": "direct",
        "purpose": "ADD a new empty field to a layer",
        "params": {
            "layer": "string, required",
            "field_name": "string, required",
            "field_type": "int, default=6 (6=Float, 2=Integer, 10=String)"
        }
    },
    "calculate_field": {
        "type": "direct",
        "purpose": "CALCULATE/UPDATE a field using a QGIS expression",
        "when": "Always for computing area, surface, length, perimeter. NEVER use run_algorithm for this.",
        "params": {
            "layer": "string, required, target layer name",
            "field_name": "string, required, field to populate",
            "expression": "string, required, QGIS expression like '$area/10000' or '$length'",
            "field_type": "int, default=6 (6=Float, 2=Integer, 10=String)"
        },
        "examples": [
            {"field_name": "surface_ha", "expression": "$area / 10000", "field_type": 6},
            {"field_name": "longueur_m", "expression": "$length", "field_type": 6}
        ]
    },
    "group_layers": {
        "type": "direct",
        "purpose": "GROUP layers into a group",
        "params": {"group_name": "string, required", "layers": "list, required, layer names"}
    },
    "create_vector_layer": {
        "type": "direct",
        "purpose": "Create an in-memory vector layer",
        "params": {
            "name": "string, required",
            "geometry_type": "string, default='Point' (Point, LineString, Polygon)",
            "crs": "string, default='EPSG:2154'",
            "fields": "list, optional, [{'name':'id','type':'integer'}]"
        }
    },
    "create_raster_layer": {
        "type": "direct",
        "purpose": "Create an in-memory raster layer",
        "params": {"name": "string, required", "width": "int, default=100", "height": "int, default=100"}
    },
    "run_algorithm": {
        "type": "processing",
        "purpose": "Run a QGIS Processing algorithm (buffer, clip, merge, dissolve, etc.)",
        "when": "ONLY for real Processing algorithms like 'native:buffer', 'native:clip', 'gdal:*'. DO NOT use for direct tools like calculate_field, export_layer.",
        "params": {
            "algorithm": "string, required, algorithm ID like 'native:buffer' or 'gdal:cliprasterbyextent'",
            "parameters": "dict, required, algorithm-specific params like {INPUT, DISTANCE, OUTPUT}"
        },
        "common_algorithms": {
            "native:buffer": {"INPUT": "layer_name", "DISTANCE": 100, "OUTPUT": "memory:"},
            "native:clip": {"INPUT": "layer", "OVERLAY": "clip_layer", "OUTPUT": "memory:"},
            "native:dissolve": {"INPUT": "layer", "OUTPUT": "memory:"},
            "native:mergevectorlayers": {"LAYERS": ["layer1", "layer2"], "OUTPUT": "memory:"},
            "native:reprojectlayer": {"INPUT": "layer", "TARGET_CRS": "EPSG:2154", "OUTPUT": "memory:"}
        }
    },
    "list_algorithms": {
        "type": "direct",
        "purpose": "LIST all available Processing algorithms",
        "params": {}
    },
    "search_algorithms": {
        "type": "direct",
        "purpose": "SEARCH processing algorithms by keyword",
        "params": {"query": "string, required"}
    },
    "export_layer": {
        "type": "direct",
        "purpose": "EXPORT a vector layer to file (GeoJSON, GPKG, SHP)",
        "when": "Use for saving data to disk. NEVER use run_algorithm for exports.",
        "params": {
            "layer": "string, required, layer name to export",
            "output_path": "string, required, full output file path",
            "format": "string, default='gpkg' (gpkg, geojson, shp)"
        }
    },
    "import_layer": {
        "type": "direct",
        "purpose": "IMPORT a vector layer from file into the project",
        "params": {"path": "string, required", "name": "string, optional"}
    },
    "zoom_to_layer": {
        "type": "direct", "purpose": "ZOOM the map canvas to a layer",
        "params": {"layer": "string, required"}
    },
    "zoom_to_extent": {
        "type": "direct", "purpose": "ZOOM to specific coordinates",
        "params": {"xmin": "float, required", "ymin": "float, required", "xmax": "float, required", "ymax": "float, required"}
    },
    "set_crs": {
        "type": "direct", "purpose": "SET the project CRS",
        "params": {"crs": "string, required, like 'EPSG:2154'"}
    },
    "refresh_canvas": {
        "type": "direct", "purpose": "REFRESH the map canvas display",
        "params": {}
    },
    "list_directory": {
        "type": "direct", "purpose": "LIST files in a directory",
        "params": {"path": "string, required", "pattern": "string, optional, glob like '*.shp'", "recursive": "bool, default=False"}
    },
    "run_command": {
        "type": "direct", "purpose": "RUN a system command",
        "params": {"command": "string, required", "timeout": "int, default=30, seconds"}
    },
}


def _classify_error(msg, tool_name=None, params=None):
    msg_lower = msg.lower()
    if "file not found" in msg_lower or "not found" in msg_lower and ":" in msg:
        return {"category": "file_not_found", "message": msg, "suggestion": "Vérifie que le fichier existe au chemin indiqué"}
    if "layer not found" in msg_lower or "layer" in msg_lower and "not found" in msg_lower:
        return {"category": "layer_not_found", "message": msg, "suggestion": "Utilise list_layers pour voir les noms exacts des couches"}
    if "algorithm" in msg_lower and "not found" in msg_lower:
        return {"category": "algorithm_not_found", "message": msg, "suggestion": "Utilise le bon outil direct (calculate_field, export_layer) au lieu d'un algorithme Processing"}
    if "is required" in msg_lower or "required" in msg_lower:
        param = msg.split("'")[1] if "'" in msg else "unknown"
        return {"category": "missing_param", "message": msg, "suggestion": f"Ajoute le paramètre requis '{param}'"}
    if "unknown tool" in msg_lower or "unknown" in msg_lower:
        return {"category": "unknown_tool", "message": msg, "suggestion": "Vérifie le nom de l'outil dans la liste des outils disponibles"}
    if "path" in msg_lower and "invalid" in msg_lower or "path" in msg_lower and "required" in msg_lower:
        return {"category": "invalid_path", "message": msg, "suggestion": "Le chemin du fichier est invalide ou manquant"}
    return {"category": "unknown", "message": msg, "suggestion": ""}


class ToolRegistry:
    def __init__(self):
        self._tools = {}
        self._descriptions = {}

    def register(self, name, func, description=""):
        self._tools[name] = func
        self._descriptions[name] = description

    def get(self, name):
        return self._tools.get(name)

    def has(self, name):
        return name in self._tools

    def list_tools(self):
        return list(self._tools.keys())

    def get_descriptions(self):
        return dict(self._descriptions)

    def get_tools_with_descriptions(self):
        return [(n, self._descriptions[n]) for n in sorted(self._tools) if n in self._descriptions]

    def get_signature(self, name):
        return SIGNATURES.get(name, None)

    def get_signature_prompt(self, user_query=""):
        lines = []
        tools = self._filter_tools(user_query) if user_query else [(n, self._descriptions[n]) for n in sorted(self._tools) if n in self._descriptions]

        direct_tools = []
        processing_tools = []
        for name, _ in tools:
            sig = SIGNATURES.get(name)
            if sig and sig.get("type") == "processing":
                processing_tools.append(name)
            else:
                direct_tools.append(name)

        if direct_tools:
            lines.append("## DIRECT TOOLS (use directly by name, NOT via run_algorithm):")
            for name in direct_tools:
                sig = SIGNATURES.get(name, {})
                desc = sig.get("purpose", self._descriptions.get(name, ""))
                params = sig.get("params", {})
                when = sig.get("when", "")
                lines.append(f"\n### {name}")
                lines.append(f"  Purpose: {desc}")
                if when:
                    lines.append(f"  When: {when}")
                if params:
                    lines.append("  Parameters:")
                    for pname, pdesc in params.items():
                        lines.append(f"    - {pname}: {pdesc}")
                examples = sig.get("examples")
                if examples:
                    lines.append("  Examples:")
                    for ex in examples:
                        ex_str = ", ".join(f"{k}={v}" for k, v in ex.items())
                        lines.append(f"    - {ex_str}")

        if processing_tools:
            lines.append("\n## PROCESSING ALGORITHMS (use via run_algorithm only):")
            for name in processing_tools:
                sig = SIGNATURES.get(name, {})
                desc = sig.get("purpose", self._descriptions.get(name, ""))
                when = sig.get("when", "")
                lines.append(f"\n### {name}")
                lines.append(f"  Purpose: {desc}")
                if when:
                    lines.append(f"  When: {when}")
                params = sig.get("params", {})
                if params:
                    lines.append("  Parameters:")
                    for pname, pdesc in params.items():
                        lines.append(f"    - {pname}: {pdesc}")
                common = sig.get("common_algorithms")
                if common:
                    lines.append("  Common algorithms (use as 'algorithm' parameter):")
                    for algo_id, algo_params in common.items():
                        pstr = ", ".join(f"{k}={v}" for k, v in algo_params.items())
                        lines.append(f"    - {algo_id}: {pstr}")

        return "\n".join(lines)

    def get_description_for_llm(self, user_query=""):
        return self.get_signature_prompt(user_query)

    def _filter_tools(self, query):
        query_lower = query.lower()
        matched = set()
        for tool_name, keywords in TOOL_KEYWORDS.items():
            if tool_name not in self._tools:
                continue
            for kw in keywords:
                if kw.lower() in query_lower:
                    matched.add(tool_name)
                    break
        if not matched:
            return [(n, self._descriptions[n]) for n in sorted(self._tools) if n in self._descriptions]
        essentials = {"create_project", "open_project", "save_project", "list_layers", "get_project_info"}
        for e in essentials:
            if e in self._tools:
                matched.add(e)
        return [(n, self._descriptions[n]) for n in sorted(matched) if n in self._descriptions]

    ALIAS_PARAM_MAPS = {
        "calculate_field": {"INPUT": "layer", "FIELD_NAME": "field_name", "EXPRESSION": "expression", "FIELD_TYPE": "field_type"},
        "add_field": {"INPUT": "layer", "FIELD_NAME": "field_name", "FIELD_TYPE": "field_type"},
        "export_layer": {"INPUT": "layer", "OUTPUT": "output_path"},
        "select_by_expression": {"INPUT": "layer", "EXPRESSION": "expression"},
    }

    def execute(self, name, parameters, context=None):
        resolved_name = name
        resolved_params = parameters

        algo = parameters.get("algorithm") if isinstance(parameters, dict) else None
        if name == "run_algorithm" and algo in self._tools:
            resolved_name = algo
            algo_params = parameters.get("parameters", {})
            if isinstance(algo_params, dict):
                pmap = self.ALIAS_PARAM_MAPS.get(algo, {})
                resolved_params = {pmap.get(k, k): v for k, v in algo_params.items()}

        func = self.get(resolved_name)
        if func is None:
            return {"status": "error", "message": f"Unknown tool: {resolved_name}"}
        try:
            QCoreApplication.processEvents()
            result = func(resolved_params, context)
            QCoreApplication.processEvents()
            return result
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": str(e),
                "traceback": traceback.format_exc(),
            }
