from qgis.core import QgsProject, QgsRectangle, QgsCoordinateReferenceSystem
from qgis.utils import iface


def _find_layer(name_or_path):
    proj = QgsProject.instance()
    for lid, layer in proj.mapLayers().items():
        if layer.name() == name_or_path or lid == name_or_path:
            return layer
    return None


def register_canvas_tools(registry):

    def zoom_to_layer(params, ctx):
        name = params.get("layer") or params.get("name")
        if name:
            layer = _find_layer(name)
            if not layer:
                return {"status": "error", "message": f"Layer not found: {name}"}
            iface.mapCanvas().setExtent(layer.extent())
        else:
            iface.mapCanvas().zoomToFullExtent()
        iface.mapCanvas().refresh()
        return {"status": "ok", "message": f"Zoomed to: {name or 'full extent'}"}

    def zoom_to_extent(params, ctx):
        xmin = params.get("xmin")
        xmax = params.get("xmax")
        ymin = params.get("ymin")
        ymax = params.get("ymax")
        if None in (xmin, xmax, ymin, ymax):
            return {"status": "error", "message": "xmin, xmax, ymin, ymax are required"}
        rect = QgsRectangle(float(xmin), float(ymin), float(xmax), float(ymax))
        iface.mapCanvas().setExtent(rect)
        iface.mapCanvas().refresh()
        return {"status": "ok", "message": f"Zoomed to extent: {xmin},{ymin} -> {xmax},{ymax}"}

    def set_crs(params, ctx):
        crs_code = params.get("crs")
        if not crs_code:
            return {"status": "error", "message": "crs is required (e.g. EPSG:2154)"}
        crs = QgsCoordinateReferenceSystem(crs_code)
        if not crs.isValid():
            return {"status": "error", "message": f"Invalid CRS: {crs_code}"}
        QgsProject.instance().setCrs(crs)
        iface.mapCanvas().setDestinationCrs(crs)
        iface.mapCanvas().refresh()
        return {"status": "ok", "message": f"Set project CRS to: {crs.authid()}"}

    def refresh_canvas(params, ctx):
        iface.mapCanvas().refresh()
        return {"status": "ok", "message": "Canvas refreshed"}

    registry.register(
        "zoom_to_layer",
        zoom_to_layer,
        "Zoom to layer. params: layer",
    )
    registry.register(
        "zoom_to_extent",
        zoom_to_extent,
        "Zoom to coordinates. params: xmin, ymin, xmax, ymax",
    )
    registry.register(
        "set_crs",
        set_crs,
        "Set project CRS. params: crs",
    )
    registry.register(
        "refresh_canvas",
        refresh_canvas,
        "Refresh map canvas. params: none",
    )
