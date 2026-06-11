from qgis.core import QgsApplication, QgsProcessingFeedback, QgsProcessingContext, QgsProject
from qgis.analysis import QgsNativeAlgorithms


class ProcessingFeedback(QgsProcessingFeedback):
    def __init__(self):
        super().__init__()
        self.logs = []
        self._progress = 0

    def pushInfo(self, info):
        self.logs.append(("info", info))

    def reportError(self, error, fatal=False):
        self.logs.append(("error" if not fatal else "fatal", error))

    def setProgressText(self, text):
        self.logs.append(("progress", text))

    def setProgress(self, progress):
        self._progress = progress


def register_processing_tools(registry):

    def run_algorithm(params, ctx):
        algorithm = params.get("algorithm")
        alg_params = params.get("parameters", params.get("params", {}))
        if not algorithm:
            return {"status": "error", "message": "algorithm name is required"}

        alg = QgsApplication.processingRegistry().algorithmById(algorithm)
        if not alg:
            fuzzy = _find_algorithm_fuzzy(algorithm)
            if fuzzy:
                if fuzzy.startswith("__hint__:"):
                    hint = fuzzy.split(":", 1)[1]
                    return {"status": "error", "message": hint}
                algorithm = fuzzy
                alg = QgsApplication.processingRegistry().algorithmById(algorithm)
            if not alg:
                available = _list_algorithms()
                return {
                    "status": "error",
                    "message": f"Algorithm '{algorithm}' not found. Available: {available[:10]}...",
                }

        feedback = ProcessingFeedback()
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())

        try:
            result = alg.run(alg_params, context, feedback)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Execution error: {e}",
                "logs": feedback.logs[-10:],
            }

        return {
            "status": "ok",
            "message": f"Algorithm '{algorithm}' executed successfully",
            "result": str(result) if result else "None",
            "logs": feedback.logs[-10:],
        }

    def list_algorithms(params, ctx):
        return {
            "status": "ok",
            "algorithms": _list_algorithms(),
        }

    def search_algorithms(params, ctx):
        query = params.get("query", "").lower()
        registry = QgsApplication.processingRegistry()
        results = []
        for alg in registry.algorithms():
            if query in alg.displayName().lower() or query in alg.id().lower():
                results.append({
                    "id": alg.id(),
                    "name": alg.displayName(),
                    "group": alg.group(),
                })
        return {
            "status": "ok",
            "count": len(results),
            "algorithms": results[:50],
        }

    registry.register(
        "run_algorithm",
        run_algorithm,
        "Run a QGIS Processing algorithm (native:buffer, native:clip, gdal:*). ONLY for real algorithms, NOT for direct tools like calculate_field. params: algorithm, parameters (INPUT, DISTANCE, OUTPUT)",
    )
    registry.register(
        "list_algorithms",
        list_algorithms,
        "List all algorithms. params: none",
    )
    registry.register(
        "search_algorithms",
        search_algorithms,
        "Search algorithms by name. params: query",
    )


ALIASES = {
    "native:area": "native:fieldcalculator",
    "qgis:area": "native:fieldcalculator",
    "native:buffer": "native:buffer",
    "qgis:buffer": "native:buffer",
    "native:clip": "native:clip",
    "qgis:clip": "native:clip",
    "native:intersection": "native:intersection",
    "qgis:intersection": "native:intersection",
    "native:union": "native:union",
    "qgis:union": "native:union",
    "native:dissolve": "native:dissolve",
    "qgis:dissolve": "native:dissolve",
    "native:fieldcalculator": "native:fieldcalculator",
    "qgis:fieldcalculator": "native:fieldcalculator",
    "native:reprojectlayer": "native:reprojectlayer",
    "qgis:reprojectlayer": "native:reprojectlayer",
    "native:centroids": "native:centroids",
    "qgis:centroids": "qgis:centroids",
    "native:simplifygeometries": "native:simplifygeometries",
    "qgis:simplifygeometries": "native:simplifygeometries",
    "native:multiparttosingleparts": "native:multiparttosingleparts",
    "qgis:multiparttosingleparts": "native:multiparttosingleparts",
    "native:singletomultiparts": "native:singletomultiparts",
    "qgis:singletomultiparts": "native:singletomultiparts",
    "native:mergevectorlayers": "native:mergevectorlayers",
    "qgis:mergevectorlayers": "native:mergevectorlayers",
    "native:splitwithlines": "native:splitwithlines",
    "qgis:splitwithlines": "native:splitwithlines",
    "native:fixgeometries": "native:fixgeometries",
    "qgis:fixgeometries": "native:fixgeometries",
}

COMMON_TASKS = {
    "area": "Use calculate_field with expression '$area' instead of run_algorithm",
    "surface": "Use calculate_field with expression '$area' instead of run_algorithm",
    "centroid": "Use native:centroids algorithm",
    "buffer": "Use native:buffer algorithm",
    "clip": "Use native:clip algorithm",
    "dissolve": "Use native:dissolve algorithm",
    "intersect": "Use native:intersection algorithm",
    "reproject": "Use native:reprojectlayer algorithm",
    "field calc": "Use native:fieldcalculator algorithm",
}


def _find_algorithm_fuzzy(name):
    registry = QgsApplication.processingRegistry()
    name_lower = name.lower()

    if name_lower in ALIASES:
        resolved = ALIASES[name_lower]
        if resolved != name_lower:
            return resolved

    for key, alias in ALIASES.items():
        if name_lower in key.lower():
            return alias

    best_match = None
    best_score = 0
    for alg in registry.algorithms():
        scores = []
        if name_lower in alg.displayName().lower():
            scores.append(10)
        if name_lower in alg.id().lower():
            scores.append(10)
        words = name_lower.replace(":", " ").replace("_", " ").split()
        for w in words:
            if len(w) > 2 and w in alg.displayName().lower():
                scores.append(5)
            if len(w) > 2 and w in alg.id().lower():
                scores.append(5)
        total = sum(scores)
        if total > best_score:
            best_score = total
            best_match = alg.id()

    if best_score >= 10:
        return best_match

    for task, hint in COMMON_TASKS.items():
        if task in name_lower:
            return f"__hint__:{hint}"

    return None


def _list_algorithms():
    registry = QgsApplication.processingRegistry()
    return [
        {"id": alg.id(), "name": alg.displayName(), "group": alg.group()}
        for alg in sorted(registry.algorithms(), key=lambda a: a.id())
    ]
