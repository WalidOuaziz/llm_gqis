from .qgis_llm_agent import QgisLlmAgentPlugin

def classFactory(iface):
    return QgisLlmAgentPlugin(iface)
