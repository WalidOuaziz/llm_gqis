import os
import json
from pathlib import Path

from qgis.core import QgsApplication, Qgis
from qgis.gui import QgisInterface
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

from .ui.chat_dock import ChatDock
from .engine.registry import ToolRegistry
from .engine.executor import ExecutionEngine
from .engine.tools import register_all_tools
from .llm.client import LlmClient
from .llm.parser import parse_llm_response
from .safety.validator import validate_plan_schema, check_destructive, validate_file_path
from .utils.logger import ExecutionLogger


SETTINGS_PREFIX = "qgis_llm_agent"


class QgisLlmAgentPlugin:
    def __init__(self, iface: QgisInterface):
        self.iface = iface
        self.dock = None
        self.action = None

        self.logger = ExecutionLogger()
        self.registry = ToolRegistry()
        self.executor = ExecutionEngine(self.registry, self.logger)
        self.validator = type("Validator", (), {
            "validate_plan_schema": staticmethod(validate_plan_schema),
            "check_destructive": staticmethod(check_destructive),
            "validate_file_path": staticmethod(validate_file_path),
        })()
        self.parser = type("Parser", (), {
            "parse_llm_response": staticmethod(parse_llm_response),
        })()

        self._load_config()

        register_all_tools(self.registry)

        self.logger.info(f"QGIS LLM Agent initialized. Tools: {len(self.registry.list_tools())}")

    def _load_config(self):
        config_path = self._config_path()
        if config_path.exists():
            try:
                with open(config_path) as f:
                    self.config = json.load(f)
            except Exception:
                self.config = self._default_config()
        else:
            self.config = self._default_config()
            self._save_config()

        self.llm_client = LlmClient(self.config)

    def _default_config(self):
        return {
            "endpoint": "http://localhost:11434/api/chat",
            "model": "qwen2.5:3b",
            "api_key": "",
            "planner_temperature": 0.3,
            "fixer_endpoint": "http://localhost:11434/api/chat",
            "fixer_model": "qwen2.5:3b",
            "fixer_api_key": "",
            "fixer_temperature": 0.1,
            "timeout": 120,
            "temperature": 0.1,
            "max_tokens": 4000,
            "preview_before_execute": False,
            "data_dir": "",
            "output_dir": "",
        }

    def _config_path(self):
        return Path(os.path.expanduser("~")) / ".qgis_llm_agent" / "config.json"

    def _save_config(self):
        self._config_path().parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_path(), "w") as f:
            json.dump(self.config, f, indent=2)

    def get_setting(self, key, default=None):
        return self.config.get(key, default)

    def set_setting(self, key, value):
        self.config[key] = value
        self._save_config()
        llm_keys = {
            "endpoint", "model", "api_key", "timeout", "temperature", "max_tokens",
            "planner_temperature", "fixer_endpoint", "fixer_model",
            "fixer_api_key", "fixer_temperature",
        }
        if key in llm_keys:
            self.llm_client = LlmClient(self.config)

    def initGui(self):
        self.dock = ChatDock(self)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.show()
        self.dock.raise_()

        self.action = QAction("QGIS LLM Agent", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setChecked(True)
        self.action.toggled.connect(self.toggle_dock)
        self.iface.addPluginToMenu("LLM Agent", self.action)

        tb = self.iface.addToolBar("QGIS LLM Agent")
        tb.setObjectName("QgisLlmAgent")
        tb.addAction(self.action)
        tb.show()

        self.logger.info("Plugin GUI initialized")

    def unload(self):
        if self.dock:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
        if self.action:
            self.iface.removePluginMenu("LLM Agent", self.action)
        self.logger.info("Plugin unloaded")

    def toggle_dock(self, checked):
        self.dock.setVisible(checked)
