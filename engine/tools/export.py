from pathlib import Path

from qgis.core import (
    QgsVectorLayer,
    QgsVectorFileWriter,
    QgsCoordinateTransformContext,
    QgsProject,
    QgsMapLayer,
)
from qgis.PyQt.QtCore import QCoreApplication


def _find_layer(name_or_path):
    proj = QgsProject.instance()
    for lid, layer in proj.mapLayers().items():
        if layer.name() == name_or_path or lid == name_or_path:
            return layer
    name_lower = name_or_path.lower().replace(" ", "_")
    for lid, layer in proj.mapLayers().items():
        if layer.name().lower().replace(" ", "_") == name_lower:
            return layer
    return None


SAVE_OPTIONS = QgsVectorFileWriter.SaveVectorOptions()


def register_export_tools(registry):

    def export_layer(params, ctx):
        name = params.get("layer") or params.get("name")
        output_path = params.get("output_path") or params.get("path")
        format_name = params.get("format", params.get("output_format", "gpkg")).lower()

        if not name:
            return {"status": "error", "message": "layer name is required"}
        layer = _find_layer(name)
        if not layer:
            return {"status": "error", "message": f"Layer not found: {name}"}
        if not isinstance(layer, QgsVectorLayer):
            return {"status": "error", "message": "Export is only supported for vector layers"}

        if not output_path:
            ext_map = {"gpkg": ".gpkg", "shp": ".shp", "geojson": ".geojson", "json": ".geojson"}
            ext = ext_map.get(format_name, ".gpkg")
            output_path = str(Path.home() / f"export_{layer.name()}{ext}")

        out_path = Path(output_path)
        if out_path.exists():
            out_path.unlink()

        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = _get_driver(format_name)

        if opts.driverName == "GPKG":
            opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

        error, new_filename, new_layer, error_msg = QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, str(out_path), QgsCoordinateTransformContext(), opts
        )

        if error == QgsVectorFileWriter.NoError:
            return {
                "status": "ok",
                "message": f"Exported '{name}' to: {out_path}",
                "path": str(out_path),
                "format": format_name,
            }
        return {"status": "error", "message": f"Export failed: {error_msg}"}

    def import_layer(params, ctx):
        path = params.get("path")
        name = params.get("name", Path(path).stem if path else None)
        if not path:
            return {"status": "error", "message": "path is required"}
        p = Path(path)
        if not p.exists():
            return {"status": "error", "message": f"File not found: {path}"}
        layer = QgsVectorLayer(str(p), name, "ogr")
        if not layer.isValid():
            return {"status": "error", "message": f"Failed to load: {path}"}
        QgsProject.instance().addMapLayer(layer)
        return {"status": "ok", "message": f"Imported: {name}", "layer_id": layer.id()}

    registry.register(
        "export_layer",
        export_layer,
        "Export vector layer to file. params: layer, output_path, format",
    )
    registry.register(
        "import_layer",
        import_layer,
        "Import vector layer from file. params: path, name",
    )


def _get_driver(format_name):
    drivers = {
        "gpkg": "GPKG",
        "geopackage": "GPKG",
        "shp": "ESRI Shapefile",
        "shapefile": "ESRI Shapefile",
        "geojson": "GeoJSON",
        "json": "GeoJSON",
        "csv": "CSV",
        "kml": "KML",
        "dxf": "DXF",
    }
    return drivers.get(format_name, "GPKG")
