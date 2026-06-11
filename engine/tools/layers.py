import os
import random
from pathlib import Path

from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsProject,
    QgsMapLayer,
    QgsFeatureRequest,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsField,
    QgsFields,
    QgsVectorFileWriter,
    QgsCoordinateReferenceSystem,
    QgsLayerTreeGroup,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsCoordinateTransformContext,
)
from qgis.PyQt.QtCore import QVariant
from osgeo import gdal, osr
import numpy as np


def _find_layer(name_or_path):
    proj = QgsProject.instance()
    for lid, layer in proj.mapLayers().items():
        if layer.name() == name_or_path or lid == name_or_path:
            return layer
        src = layer.source()
        p = Path(src)
        if p.stem == name_or_path or str(p) == name_or_path:
            return layer
    return None


def register_layer_tools(registry):

    def create_vector_layer(params, ctx):
        name = params.get("name", "new_layer")
        geometry_type = params.get("geometry_type", params.get("type", "point")).lower()
        crs = params.get("crs", "EPSG:2154")
        fields_list = params.get("fields", [{"name": "id", "type": "int"}])
        features_count = params.get("features", 5)

        geom_map = {
            "point": "Point", "points": "Point", "pt": "Point",
            "line": "LineString", "lines": "LineString", "polyline": "LineString",
            "polylines": "LineString", "linestring": "LineString",
            "polygon": "Polygon", "polygons": "Polygon", "poly": "Polygon",
        }

        pipe_separated = [g.strip() for g in geometry_type.split("|") if g.strip()]
        if len(pipe_separated) > 1:
            results = []
            base_name = name.rsplit("_", 1)[0] if "_" in name else name
            for i, gt in enumerate(pipe_separated):
                sub_params = dict(params)
                sub_params["geometry_type"] = gt
                sub_params["name"] = f"{base_name}_{gt}s" if not any(c.isdigit() for c in gt) else f"{base_name}_{i}"
                sub_params["features"] = max(1, features_count // len(pipe_separated))
                sub_result = create_vector_layer(sub_params, ctx)
                results.append(sub_result)
            ok_count = sum(1 for r in results if r["status"] == "ok")
            errors = [r["message"] for r in results if r["status"] == "error"]
            return {
                "status": "ok" if ok_count > 0 else "error",
                "message": f"Created {ok_count}/{len(results)} layers: {', '.join(r.get('message','?') for r in results)}",
                "errors": errors,
            }

        qgis_geom = geom_map.get(geometry_type)
        if not qgis_geom:
            return {"status": "error", "message": f"Invalid geometry type: {geometry_type}. Valid: point, line, polygon. For multiple types, pipe-separate them: 'point|polygon|line'"}

        layer = QgsVectorLayer(f"{qgis_geom}?crs={crs}", name, "memory")
        pr = layer.dataProvider()

        for fd in fields_list:
            fname = fd.get("name", "field")
            ftype = fd.get("type", "int").lower()
            type_map = {"int": QVariant.Int, "integer": QVariant.Int, "float": QVariant.Double,
                        "double": QVariant.Double, "string": QVariant.String, "text": QVariant.String,
                        "bool": QVariant.Bool}
            qt = type_map.get(ftype, QVariant.Int)
            pr.addAttributes([QgsField(fname, qt)])
        layer.updateFields()

        for i in range(features_count):
            f = QgsFeature()
            attrs = [i]
            for fd in fields_list[1:]:
                attrs.append(fd.get("name", f"f{i}"))
            f.setAttributes(attrs)
            if qgis_geom == "Point":
                f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(random.randint(0,1000), random.randint(0,1000))))
            elif qgis_geom == "LineString":
                pts = [QgsPointXY(random.randint(0,1000), random.randint(0,1000)) for _ in range(3)]
                f.setGeometry(QgsGeometry.fromPolylineXY(pts))
            elif qgis_geom == "Polygon":
                pts = [QgsPointXY(random.randint(0,1000), random.randint(0,1000)) for _ in range(4)]
                pts.append(pts[0])
                f.setGeometry(QgsGeometry.fromPolygonXY([pts]))
            pr.addFeature(f)

        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        return {"status": "ok", "message": f"Created {qgis_geom} layer '{name}' with {features_count} feature(s) and {len(fields_list)} field(s)", "layer_id": layer.id()}

    def create_raster_layer(params, ctx):
        name = params.get("name", "new_raster")
        width = params.get("width", 100)
        height = params.get("height", 100)
        crs = params.get("crs", "EPSG:2154")
        value = params.get("value", 1)

        tmp_dir = os.path.join(str(Path.home()), ".qgis_llm_agent", "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        tif_path = os.path.join(tmp_dir, f"{name}.tif")

        try:
            from osgeo import gdal, osr
            import numpy as np
            arr = np.full((height, width), value, dtype=np.float32)
            driver = gdal.GetDriverByName("GTiff")
            ds = driver.Create(tif_path, width, height, 1, gdal.GDT_Float32)
            srs = osr.SpatialReference()
            srs.SetFromUserInput(crs)
            ds.SetProjection(srs.ExportToWkt())
            ds.SetGeoTransform([0, 10, 0, 0, 0, -10])
            ds.GetRasterBand(1).WriteArray(arr)
            ds.FlushCache()
            ds = None
        except Exception as e:
            return {"status": "error", "message": f"Failed to create raster: {e}"}

        layer = QgsRasterLayer(tif_path, name, "gdal")
        if not layer.isValid():
            return {"status": "error", "message": f"Created file but failed to load raster: {tif_path}"}

        QgsProject.instance().addMapLayer(layer)
        return {"status": "ok", "message": f"Created raster layer '{name}' ({width}x{height})", "layer_id": layer.id()}

    def add_vector_layer(params, ctx):
        path = params.get("path")
        if not path:
            return {"status": "error", "message": "path is required"}
        name = params.get("name", Path(path).stem)
        provider = params.get("provider", "ogr")
        layer = QgsVectorLayer(str(path), name, provider)
        if not layer.isValid():
            return {"status": "error", "message": f"Failed to load vector layer: {path}"}
        QgsProject.instance().addMapLayer(layer)
        return {"status": "ok", "message": f"Added layer: {name}", "layer_id": layer.id()}

    def add_raster_layer(params, ctx):
        path = params.get("path")
        if not path:
            return {"status": "error", "message": "path is required"}
        name = params.get("name", Path(path).stem)
        provider = params.get("provider", "gdal")
        layer = QgsRasterLayer(str(path), name, provider)
        if not layer.isValid():
            return {"status": "error", "message": f"Failed to load raster layer: {path}"}
        QgsProject.instance().addMapLayer(layer)
        return {"status": "ok", "message": f"Added raster layer: {name}", "layer_id": layer.id()}

    def remove_layer(params, ctx):
        name = params.get("layer") or params.get("name")
        if not name:
            return {"status": "error", "message": "layer name is required"}
        layer = _find_layer(name)
        if not layer:
            return {"status": "error", "message": f"Layer not found: {name}"}
        QgsProject.instance().removeMapLayer(layer.id())
        return {"status": "ok", "message": f"Removed layer: {name}"}

    def rename_layer(params, ctx):
        name = params.get("layer") or params.get("name")
        new_name = params.get("new_name")
        if not name or not new_name:
            return {"status": "error", "message": "layer and new_name are required"}
        layer = _find_layer(name)
        if not layer:
            return {"status": "error", "message": f"Layer not found: {name}"}
        layer.setName(new_name)
        return {"status": "ok", "message": f"Renamed '{name}' to '{new_name}'"}

    def list_layers(params, ctx):
        proj = QgsProject.instance()
        layers = proj.mapLayers().values()
        return {
            "status": "ok",
            "layers": [
                {
                    "id": l.id(),
                    "name": l.name(),
                    "type": "vector" if isinstance(l, QgsVectorLayer) else "raster",
                    "crs": l.crs().authid() if l.crs().isValid() else "unknown",
                    "feature_count": l.featureCount() if isinstance(l, QgsVectorLayer) else None,
                }
                for l in layers
            ],
        }

    def get_layer_info(params, ctx):
        name = params.get("layer") or params.get("name")
        if not name:
            return {"status": "error", "message": "layer name is required"}
        layer = _find_layer(name)
        if not layer:
            return {"status": "error", "message": f"Layer not found: {name}"}
        info = {
            "id": layer.id(),
            "name": layer.name(),
            "source": layer.source(),
            "crs": layer.crs().authid() if layer.crs().isValid() else "unknown",
            "extent": str(layer.extent().asWktPolygon()),
        }
        if isinstance(layer, QgsVectorLayer):
            info["type"] = "vector"
            info["feature_count"] = layer.featureCount()
            info["fields"] = [
                {"name": f.name(), "type": f.typeName()} for f in layer.fields()
            ]
        else:
            info["type"] = "raster"
            info["width"] = layer.width()
            info["height"] = layer.height()
        return {"status": "ok", "info": info}

    def select_by_expression(params, ctx):
        name = params.get("layer") or params.get("name")
        expression = params.get("expression")
        if not name or not expression:
            return {"status": "error", "message": "layer and expression are required"}
        layer = _find_layer(name)
        if not layer or not isinstance(layer, QgsVectorLayer):
            return {"status": "error", "message": f"Vector layer not found: {name}"}
        request = QgsFeatureRequest(QgsExpression(expression))
        ids = [f.id() for f in layer.getFeatures(request)]
        layer.selectByIds(ids)
        return {"status": "ok", "message": f"Selected {len(ids)} features", "count": len(ids)}

    def clear_selection(params, ctx):
        name = params.get("layer") or params.get("name")
        if name:
            layer = _find_layer(name)
            if layer:
                layer.removeSelection()
                return {"status": "ok", "message": f"Selection cleared on: {name}"}
        proj = QgsProject.instance()
        for l in proj.mapLayers().values():
            if isinstance(l, QgsVectorLayer):
                l.removeSelection()
        return {"status": "ok", "message": "All selections cleared"}

    def add_field(params, ctx):
        name = params.get("layer") or params.get("name")
        field_name = params.get("field_name")
        field_type = params.get("field_type", "string")
        length = params.get("length", 255)
        if not name or not field_name:
            return {"status": "error", "message": "layer and field_name are required"}
        layer = _find_layer(name)
        if not layer or not isinstance(layer, QgsVectorLayer):
            return {"status": "error", "message": f"Vector layer not found: {name}"}
        type_map = {
            "string": QVariant.String,
            "int": QVariant.Int,
            "integer": QVariant.Int,
            "float": QVariant.Double,
            "double": QVariant.Double,
            "bool": QVariant.Bool,
        }
        qt_type = type_map.get(field_type.lower(), QVariant.String)
        field = QgsField(field_name, qt_type)
        field.setLength(length)
        layer.dataProvider().addAttributes([field])
        layer.updateFields()
        return {"status": "ok", "message": f"Added field '{field_name}' to '{layer.name()}'"}

    def calculate_field(params, ctx):
        name = params.get("layer") or params.get("name")
        field_name = params.get("field_name") or params.get("field")
        expression = params.get("expression")
        field_type = params.get("field_type", "float")
        if not name or not field_name or not expression:
            return {"status": "error", "message": "layer, field_name, and expression are required"}
        layer = _find_layer(name)
        if not layer or not isinstance(layer, QgsVectorLayer):
            return {"status": "error", "message": f"Vector layer not found: {name}"}
        try:
            expr = QgsExpression(expression)
            if expr.hasParserError():
                return {"status": "error", "message": f"Expression error: {expr.parserErrorString()}"}
            ctx = QgsExpressionContext()
            ctx.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(layer))
            type_map = {
                "string": QVariant.String,
                "int": QVariant.Int,
                "integer": QVariant.Int,
                "float": QVariant.Double,
                "double": QVariant.Double,
                "bool": QVariant.Bool,
            }
            qt_type = type_map.get(field_type.lower(), QVariant.Double)
            field_idx = layer.fields().lookupField(field_name)
            if field_idx == -1:
                field = QgsField(field_name, qt_type)
                layer.dataProvider().addAttributes([field])
                layer.updateFields()
                field_idx = layer.fields().lookupField(field_name)
            layer.startEditing()
            for f in layer.getFeatures():
                ctx.setFeature(f)
                val = expr.evaluate(ctx)
                if expr.hasEvalError():
                    continue
                layer.changeAttributeValue(f.id(), field_idx, val)
            layer.commitChanges()
            return {"status": "ok", "message": f"Calculated {field_name} = {expression} on {layer.name()}"}
        except Exception as e:
            return {"status": "error", "message": f"Calculation failed: {e}"}

    def group_layers(params, ctx):
        group_name = params.get("group_name")
        layer_names = params.get("layers", [])
        if not group_name:
            return {"status": "error", "message": "group_name is required"}
        root = QgsProject.instance().layerTreeRoot()
        group = root.addGroup(group_name)
        for ln in layer_names:
            layer = _find_layer(ln)
            if layer:
                ltl = root.findLayer(layer.id())
                if ltl:
                    clone = ltl.clone()
                    group.addChildNode(clone)
                    root.removeChildNode(ltl)
        return {"status": "ok", "message": f"Created group '{group_name}' with {len(layer_names)} layers"}

    registry.register(
        "create_vector_layer",
        create_vector_layer,
        "Create an in-memory vector layer. params: name, geometry_type, crs, fields, features",
    )
    registry.register(
        "create_raster_layer",
        create_raster_layer,
        "Create an in-memory raster layer. params: name, width, height, crs, value",
    )
    registry.register(
        "add_layer",
        add_vector_layer,
        "Load a vector layer from file. params: path, name, provider",
    )
    registry.register(
        "add_raster_layer",
        add_raster_layer,
        "Load a raster layer from file. params: path, name",
    )
    registry.register(
        "remove_layer",
        remove_layer,
        "Remove a layer. params: layer",
    )
    registry.register(
        "rename_layer",
        rename_layer,
        "Rename a layer. params: layer, new_name",
    )
    registry.register(
        "list_layers",
        list_layers,
        "List all layers. params: none",
    )
    registry.register(
        "get_layer_info",
        get_layer_info,
        "Get layer info. params: layer",
    )
    registry.register(
        "select_by_expression",
        select_by_expression,
        "Select features by expression. params: layer, expression",
    )
    registry.register(
        "clear_selection",
        clear_selection,
        "Clear selection. params: layer",
    )
    registry.register(
        "add_field",
        add_field,
        "Add a field to a layer. params: layer, field_name, field_type",
    )
    registry.register(
        "calculate_field",
        calculate_field,
        "[DIRECT TOOL] Add/update a field with QGIS expression ($area/surface/$length/$perimeter). DO NOT use run_algorithm. params: layer, field_name, expression, field_type",
    )
    registry.register(
        "group_layers",
        group_layers,
        "Group layers. params: group_name, layers",
    )
