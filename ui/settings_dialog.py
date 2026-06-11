from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QDialogButtonBox,
    QTabWidget, QWidget, QLabel,
)


class SettingsDialog(QDialog):
    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("QGIS LLM Agent - Settings")
        self.setMinimumWidth(560)
        self.setup_ui()
        self.load_config()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # --- TAB 1: Planner (main model) ---
        planner_tab = QWidget()
        planner_layout = QFormLayout(planner_tab)
        planner_layout.addRow(QLabel(
            "<b>Default:</b> qwen2.5:3b via Ollama (local)"
        ))
        self.p_endpoint = QLineEdit()
        self.p_endpoint.setPlaceholderText("http://localhost:11434/api/chat")
        planner_layout.addRow("Endpoint:", self.p_endpoint)
        self.p_model = QLineEdit()
        self.p_model.setPlaceholderText("qwen2.5:3b")
        planner_layout.addRow("Model:", self.p_model)
        self.p_key = QLineEdit()
        self.p_key.setPlaceholderText("(leave empty for Ollama)")
        self.p_key.setEchoMode(QLineEdit.Password)
        planner_layout.addRow("API Key:", self.p_key)
        self.p_temp = QDoubleSpinBox()
        self.p_temp.setRange(0.0, 2.0)
        self.p_temp.setSingleStep(0.1)
        self.p_temp.setValue(0.3)
        planner_layout.addRow("Temperature:", self.p_temp)
        tabs.addTab(planner_tab, "Planner LLM")

        # --- TAB 2: Fixer (error recovery) ---
        fix_tab = QWidget()
        fix_layout = QFormLayout(fix_tab)
        fix_layout.addRow(QLabel(
            "<b>Default:</b> qwen2.5:3b via Ollama (local)"
        ))
        self.f_endpoint = QLineEdit()
        self.f_endpoint.setPlaceholderText("http://localhost:11434/api/chat")
        fix_layout.addRow("Endpoint:", self.f_endpoint)
        self.f_model = QLineEdit()
        self.f_model.setPlaceholderText("qwen2.5:3b")
        fix_layout.addRow("Model:", self.f_model)
        self.f_key = QLineEdit()
        self.f_key.setPlaceholderText("(leave empty for Ollama)")
        self.f_key.setEchoMode(QLineEdit.Password)
        fix_layout.addRow("API Key:", self.f_key)
        self.f_temp = QDoubleSpinBox()
        self.f_temp.setRange(0.0, 2.0)
        self.f_temp.setSingleStep(0.1)
        self.f_temp.setValue(0.1)
        fix_layout.addRow("Temperature:", self.f_temp)
        tabs.addTab(fix_tab, "Fixer LLM")

        # --- TAB 3: General ---
        gen_tab = QWidget()
        gen_layout = QFormLayout(gen_tab)
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 600)
        self.timeout_spin.setSuffix(" sec")
        self.timeout_spin.setValue(120)
        gen_layout.addRow("Timeout:", self.timeout_spin)
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 32000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(4096)
        gen_layout.addRow("Max Tokens:", self.max_tokens_spin)
        self.preview_cb = QCheckBox("Show plan preview before execution")
        gen_layout.addRow("", self.preview_cb)
        tabs.addTab(gen_tab, "General")

        layout.addWidget(tabs)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.save_config)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def load_config(self):
        c = self.plugin.config
        self.p_endpoint.setText(c.get("endpoint", "http://localhost:11434/api/chat"))
        self.p_model.setText(c.get("model", "qwen2.5:3b"))
        self.p_key.setText(c.get("api_key", ""))
        self.p_temp.setValue(c.get("planner_temperature", c.get("temperature", 0.3)))
        self.f_endpoint.setText(c.get("fixer_endpoint", "http://localhost:11434/api/chat"))
        self.f_model.setText(c.get("fixer_model", "qwen2.5:3b"))
        self.f_key.setText(c.get("fixer_api_key", ""))
        self.f_temp.setValue(c.get("fixer_temperature", 0.1))
        self.timeout_spin.setValue(c.get("timeout", 120))
        self.max_tokens_spin.setValue(c.get("max_tokens", 4096))
        self.preview_cb.setChecked(c.get("preview_before_execute", False))

    def save_config(self):
        self.plugin.set_setting("endpoint", self.p_endpoint.text().strip())
        self.plugin.set_setting("model", self.p_model.text().strip())
        self.plugin.set_setting("api_key", self.p_key.text().strip())
        self.plugin.set_setting("planner_temperature", self.p_temp.value())
        self.plugin.set_setting("fixer_endpoint", self.f_endpoint.text().strip())
        self.plugin.set_setting("fixer_model", self.f_model.text().strip())
        self.plugin.set_setting("fixer_api_key", self.f_key.text().strip())
        self.plugin.set_setting("fixer_temperature", self.f_temp.value())
        self.plugin.set_setting("timeout", self.timeout_spin.value())
        self.plugin.set_setting("max_tokens", self.max_tokens_spin.value())
        self.plugin.set_setting("preview_before_execute", self.preview_cb.isChecked())
        self.accept()
