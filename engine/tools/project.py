from pathlib import Path

from qgis.core import QgsProject, QgsMessageLog, Qgis


def register_project_tools(registry):

    def create_project(params, ctx):
        QgsProject.instance().clear()
        title = params.get("title", "Untitled Project")
        QgsProject.instance().setTitle(title)
        return {"status": "ok", "message": f"Created project: {title}"}

    def open_project(params, ctx):
        path = params.get("path")
        if not path:
            return {"status": "error", "message": "path is required"}
        p = Path(path)
        if not p.exists():
            return {"status": "error", "message": f"File not found: {path}"}
        QgsProject.instance().read(str(p))
        return {"status": "ok", "message": f"Opened project: {p.name}"}

    def save_project(params, ctx):
        path = params.get("path", None)
        if path:
            QgsProject.instance().write(str(path))
            return {"status": "ok", "message": f"Project saved to: {path}"}
        else:
            QgsProject.instance().write()
            return {"status": "ok", "message": "Project saved"}

    def get_project_info(params, ctx):
        proj = QgsProject.instance()
        layers = proj.mapLayers()
        return {
            "status": "ok",
            "title": proj.title(),
            "file_name": proj.fileName(),
            "crs": proj.crs().authid() if proj.crs().isValid() else None,
            "layer_count": len(layers),
            "layers": [
                {"name": l.name(), "type": l.type().name, "crs": l.crs().authid()}
                for l in layers.values()
            ],
        }

    registry.register(
        "create_project",
        create_project,
        "CREATE a new blank project. ONLY when user says new/nouveau/créer. params: title",
    )
    registry.register(
        "open_project",
        open_project,
        "OPEN an existing project file. Use when user says ouvrir/open/load. params: path",
    )
    registry.register(
        "save_project",
        save_project,
        "SAVE current project to disk. params: path (optional)",
    )
    registry.register(
        "get_project_info",
        get_project_info,
        "Get current project info. params: none",
    )
