import json
import re
from datetime import datetime

from qgis.PyQt.QtCore import Qt, QTimer, QEvent, pyqtSignal, QObject, QThread, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QPushButton,
    QLabel,
    QProgressBar,
    QSplitter,
    QCheckBox,
)
from qgis.PyQt.QtGui import QKeySequence, QShortcut


STYLE = """
QPushButton { padding: 8px 16px; border-radius: 6px; font-size: 11pt; font-weight: bold; }
#btnSend { background-color: #1976D2; color: white; border: none; }
#btnSend:hover { background-color: #1565C0; }
#btnSend:disabled { background-color: #90CAF9; color: #BBDEFB; }
#btnClear { background-color: #f5f5f5; color: #555; border: 1px solid #ddd; }
#btnClear:hover { background-color: #e8e8e8; }
#btnConfig { background-color: #f5f5f5; color: #555; border: 1px solid #ddd; }
#btnConfig:hover { background-color: #e8e8e8; }
QTextEdit { font-family: 'Segoe UI', Consolas, monospace; font-size: 10pt; border: none; }
#inputEdit { background-color: #fafafa; border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; font-size: 11pt; }
#inputEdit:focus { border-color: #1976D2; }
#outputEdit { background-color: #fcfcfc; border: 1px solid #eee; border-radius: 6px; padding: 8px; }
QProgressBar { text-align: center; height: 8px; border-radius: 4px; border: none; background-color: #E3F2FD; }
QProgressBar::chunk { background-color: #1976D2; border-radius: 4px; }
#statusBar { background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 6px 10px; font-size: 10pt; }
QCheckBox { spacing: 6px; font-size: 10pt; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 2px solid #bbb; }
QCheckBox::indicator:checked { background-color: #1976D2; border-color: #1976D2; }
"""


class LlmSignal(QObject):
    step = pyqtSignal(int, str)
    parsed = pyqtSignal(object)
    fail = pyqtSignal(str)


GREETING_PATTERNS = ("hi", "hello", "hey", "bonjour", "salut", "test", "coucou", "yo", "good morning", "good evening")


def _build_planner_prompt(tool_desc, context_str, user_text):
    return (
        "You are a GIS automation engine. Convert natural language into executable QGIS operations.\n"
        "Think step by step, then output ONLY the final JSON.\n\n"
        "FORMAT:\n"
        "Reasoning: <1-2 short sentences analyzing what the user wants>\n"
        '{"steps":[{"tool":"...","parameters":{...}}]}\n\n'
        "Be concise in Reasoning. Do not repeat the user's question.\n\n"
        + tool_desc + "\n\n"
        "Current project context:\n"
        + context_str + "\n\n"
        "CRITICAL RULES:\n"
        "1. Output MUST be a JSON object with a 'steps' array\n"
        "2. Every step MUST have 'tool' (string) and 'parameters' (object) fields\n"
        "3. Use exact layer names from the current project (not the user prompt)\n"
        "4. Chain ALL necessary steps. Never merge operations. Each operation = one step.\n"
        "5. Use DIRECT TOOLS by name (calculate_field, export_layer, etc.). Do NOT wrap them inside run_algorithm.\n"
        "6. Only use run_algorithm for REAL Processing algorithms: native:buffer, native:clip, gdal:*, etc.\n"
        "7. If the user says hi/hello/test/greeting, return {\"steps\":[]}\n"
        "8. If unclear or impossible, return {\"steps\":[]}\n"
        "9. ONLY use create_project when user says 'new project'. For open/load use open_project.\n\n"
        "EXAMPLES:\n\n"
        "# Example 1: Buffer a layer\n"
        'User: "Buffer the roads layer by 50 meters"\n'
        "Reasoning: User wants a buffer on the roads layer. Use run_algorithm with native:buffer, distance 50, output to memory.\n"
        '{"steps":[{"tool":"run_algorithm","parameters":{"algorithm":"native:buffer","parameters":{"INPUT":"roads","DISTANCE":50,"OUTPUT":"memory:"}}}]}\n\n'
        "# Example 2: Open project, calculate field, export\n"
        'User: "Ouvre projet.qgz, calcule la surface en hectares dans un champ surface_ha pour couche_parcelles, exporte en GeoJSON"\n'
        "Reasoning: User wants 3 steps: open project, calculate field with $area/10000, export to GeoJSON. calculate_field and export_layer are DIRECT tools.\n"
        '{"steps":[{"tool":"open_project","parameters":{"path":"projet.qgz"}},{"tool":"calculate_field","parameters":{"layer":"couche_parcelles","field_name":"surface_ha","expression":"$area/10000","field_type":6}},{"tool":"export_layer","parameters":{"layer":"couche_parcelles","output_path":"export.geojson","format":"geojson"}}]}\n\n'
        "# Example 3: Create new project and import a layer\n"
        'User: "Crée un nouveau projet EPSG:2154 et importe communes.shp"\n'
        "Reasoning: Create new project, import layer from file.\n"
        '{"steps":[{"tool":"create_project","parameters":{"title":"Mon Projet"}},{"tool":"set_crs","parameters":{"crs":"EPSG:2154"}},{"tool":"add_layer","parameters":{"path":"communes.shp","name":"communes"}}]}\n\n'
        "# Example 4: List layers and get info\n"
        'User: "Liste les couches et donne les infos de la couche routier"\n'
        "Reasoning: First list all layers to discover names, then get info on the one named 'routier'.\n"
        '{"steps":[{"tool":"list_layers","parameters":{}},{"tool":"get_layer_info","parameters":{"layer":"routier"}}]}\n\n'
        "# Example 5: Complex workflow with buffer + dissolve\n"
        'User: "Crée un buffer de 100m autour des routes, puis dissout les tampons"\n'
        "Reasoning: Two processing steps: buffer then dissolve on the buffered output.\n"
        '{"steps":[{"tool":"run_algorithm","parameters":{"algorithm":"native:buffer","parameters":{"INPUT":"routes","DISTANCE":100,"OUTPUT":"memory:"}}},{"tool":"run_algorithm","parameters":{"algorithm":"native:dissolve","parameters":{"INPUT":"memory:","OUTPUT":"memory:"}}}]}\n\n'
        "# Example 6: Field calculation with expression\n"
        'User: "Ajoute un champ longueur_km pour la couche troncons et calcule la longueur en km"\n'
        "Reasoning: calculate_field is a DIRECT tool, not an algorithm.\n"
        '{"steps":[{"tool":"calculate_field","parameters":{"layer":"troncons","field_name":"longueur_km","expression":"$length/1000","field_type":6}}]}\n\n'
        "COMMON MISTAKES TO AVOID:\n"
        "- Wrong: {\"tool\":\"run_algorithm\",\"parameters\":{\"algorithm\":\"calculate_field\",...}}  (calculate_field is a DIRECT tool, not an algorithm!)\n"
        "- Wrong: {\"tool\":\"run_algorithm\",\"parameters\":{\"algorithm\":\"export_layer\",...}}  (export_layer is a DIRECT tool, not an algorithm!)\n"
        "- Wrong: Using create_project when user says 'dans ce projet' (means current project, not new)\n"
        "- Wrong: Omitting steps (e.g. not listing layers before referencing them)\n\n"
        "OUTPUT REQUIREMENTS:\n"
        "- Respond with Reasoning line then ONE JSON object on the next line\n"
        "- Do NOT add text after the JSON\n"
        "- Do NOT wrap in ```json or ```\n"
        "- Do NOT use single quotes for strings\n"
        "- Do NOT add trailing commas\n"
        "- Do NOT use unquoted keys\n"
        "- Do NOT use backslash-escaped forward slashes (use / not \\/)"
    )



FIXER_PROMPT = (
    "You are a QGIS error recovery system. A plan step failed during execution.\n"
    "Available tools: {tool_list}\n\n"
    "Original plan:\n"
    "{plan_json}\n\n"
    "Failed step:\n"
    "  tool: {failed_tool}\n"
    "  parameters: {failed_params}\n"
    "  error: {error_message}\n\n"
    "Generate a corrected execution plan (full JSON with 'steps' array) that fixes the failed step.\n"
    "Output ONLY valid JSON, no other text."
)


class LlmWorker(QThread):
    def __init__(self, plugin, user_text, context_str, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.user_text = user_text
        self.context_str = context_str
        self.sig = LlmSignal()
        self._plan = None
        self._tool_list_str = ""

    def run(self):
        try:
            user_lower = self.user_text.strip().lower()
            is_greeting = any(user_lower == g or user_lower.startswith(g + " ") or user_lower.startswith(g + "!") or user_lower.startswith(g + ",") for g in GREETING_PATTERNS)
            if is_greeting:
                self.sig.parsed.emit({"steps": []})
                return

            tool_desc = self.plugin.registry.get_description_for_llm(self.user_text)
            self._tool_list_str = ", ".join(sorted(self.plugin.registry.list_tools()))

            # --- PHASE 1: PLANNER LLM ---
            self.sig.step.emit(10, "Planner LLM: generating plan...")
            planner_prompt = _build_planner_prompt(tool_desc, self.context_str, self.user_text)
            response = self.plugin.llm_client.chat_planner(planner_prompt, self.user_text)

            self.sig.step.emit(40, "Parsing initial plan...")
            plan, error = self.plugin.parser.parse_llm_response(response)
            if error:
                self.sig.step.emit(40, "Planner LLM failed JSON. Retrying with fixer...")
                response = self.plugin.llm_client.chat_fixer(
                    "Extract the JSON object and output it exactly. No explanation, no markdown, no text before or after.",
                    response[:2000]
                )
                plan, error = self.plugin.parser.parse_llm_response(response)
                if error:
                    self.plugin.logger.error(f"LLM raw response: {response[:500]}")
                    self.sig.fail.emit(f"Planner failed: {error}")
                    return

            # --- SCHEMA VALIDATION ---
            valid, schema_error = self.plugin.validator.validate_plan_schema(plan)
            if not valid:
                self.sig.fail.emit(f"Schema validation failed: {schema_error}")
                return

            self._plan = plan
            steps = plan.get("steps", [])
            if not steps:
                self.sig.step.emit(100, "No actions needed")
                self.sig.parsed.emit(plan)
                return
            self.sig.step.emit(90, "Plan ready")
            self.sig.parsed.emit(plan)

        except Exception as e:
            import traceback
            self.sig.fail.emit(f"{e}\n{traceback.format_exc()[:500]}")


FIXER_PROMPT_UI = (
    "A QGIS plan step failed at runtime. Generate a corrected plan.\n"
    "Available tools:\n{tool_descriptions}\n\n"
    "Current project context (REAL loaded layers):\n{real_context}\n\n"
    "Original plan: {plan_json}\n"
    "Failed step {step_idx}: tool='{failed_tool}', params={failed_params}\n"
    "Error: {error_message}\n\n"
    "CRITICAL RULES:\n"
    "- Use the EXACT layer names from the project context above.\n"
    "- Use tools DIRECTLY from the list above. Do NOT wrap tool names inside run_algorithm.\n"
    "  Example: calculate_field is a tool → use {{\"tool\":\"calculate_field\",...}}\n"
    "  Only use run_algorithm for real processing algorithms like native:buffer, native:clip.\n"
    "- Fix the failed step and return the COMPLETE corrected plan.\n"
    "- Output ONLY the JSON object. No text before or after. No markdown."
)

SOLVER_PROMPT = (
    "Tu aides à corriger une erreur dans un plan QGIS.\n"
    "Propose des solutions alternatives.\n\n"
    "Contexte projet (couches REELLES chargées):\n{real_context}\n\n"
    "Étape échouée #{step_idx}: tool='{failed_tool}', params={failed_params}\n"
    "Erreur: {error_message}\n\n"
    "Requête originale: {user_query}\n\n"
    "Outils disponibles:\n{tool_descriptions}\n\n"
    "IMPORTANT: Utilise les VRAIS noms de couches du contexte ci-dessus.\n\n"
    "Réponds UNIQUEMENT avec ce JSON, sans texte autour:\n"
    '{{\n'
    '  "solutions": [\n'
    '    {{\n'
    '      "label": "Nom court",\n'
    '      "description": "Ce que fait la solution",\n'
    '      "action": {{"tool": "...", "parameters": {{...}}}}\n'
    '    }}\n'
    '  ]\n'
    '}}\n'
    "Si la solution est 'ignorer cette étape', mets 'action': null.\n"
    "Propose 2-3 solutions maximum."
)


class ChatDock(QDockWidget):
    MAX_FIXER_RETRIES = 3

    STATE_CHANGING_TOOLS = {"open_project", "add_layer", "import_layer", "create_project", "remove_layer", "rename_layer"}

    def __init__(self, plugin):
        super().__init__()
        self.plugin = plugin
        self._worker = None
        self._pending_plan = None
        self._executing = False
        self._execution_index = 0
        self._execution_steps = []
        self._execution_results = []
        self._fixer_retries = 0
        self._input_history = []
        self._history_index = -1
        self._loading_timer = None
        self._loading_dots = 0
        self._real_context = "No layers loaded."
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("QGIS LLM Agent")
        self.setStyleSheet(STYLE)

        w = QWidget()
        self.setWidget(w)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("<b>QGIS LLM Agent</b>")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-size: 14pt; padding: 6px;")
        layout.addWidget(header)

        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("inputEdit")
        self.input_edit.setPlaceholderText(
            "Describe what you want to do...  (Enter to send, Shift+Enter for new line)\n"
            'Examples:\n'
            '  "Ouvre un projet et calcule la surface"\n'
            '  "Buffer the roads layer by 50 meters"\n'
            '  "Export layers to GeoJSON"'
        )
        self.input_edit.setMaximumHeight(90)
        self.input_edit.installEventFilter(self)
        layout.addWidget(self.input_edit)

        btn_layout = QHBoxLayout()
        self.send_btn = QPushButton("Send")
        self.send_btn.setObjectName("btnSend")
        self.send_btn.clicked.connect(self.on_send)
        btn_layout.addWidget(self.send_btn)

        self.preview_cb = QCheckBox("Preview plan")
        self.preview_cb.setToolTip("Show execution plan before running")
        btn_layout.addWidget(self.preview_cb)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("btnClear")
        self.clear_btn.clicked.connect(self.on_clear)
        btn_layout.addWidget(self.clear_btn)

        self.config_btn = QPushButton("Settings")
        self.config_btn.setObjectName("btnConfig")
        self.config_btn.clicked.connect(self.on_settings)
        btn_layout.addWidget(self.config_btn)
        layout.addLayout(btn_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        layout.addWidget(self.progress)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("statusBar")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.choices_container = QWidget()
        self.choices_container.setVisible(False)
        choices_layout = QVBoxLayout(self.choices_container)
        choices_layout.setContentsMargins(4, 4, 4, 4)
        choices_layout.setSpacing(4)
        self.choices_label = QLabel()
        self.choices_label.setWordWrap(True)
        choices_layout.addWidget(self.choices_label)
        self.choices_btn_layout = QHBoxLayout()
        choices_layout.addLayout(self.choices_btn_layout)
        layout.addWidget(self.choices_container)
        self._choice_buttons = []

        output_splitter = QSplitter(Qt.Vertical)

        self.output_edit = QTextEdit()
        self.output_edit.setObjectName("outputEdit")
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText("Results will appear here...")
        output_splitter.addWidget(self.output_edit)

        self.plan_edit = QTextEdit()
        self.plan_edit.setObjectName("outputEdit")
        self.plan_edit.setReadOnly(True)
        self.plan_edit.setPlaceholderText("Execution plan preview...")
        self.plan_edit.setMaximumHeight(150)
        self.plan_edit.setVisible(False)
        output_splitter.addWidget(self.plan_edit)

        layout.addWidget(output_splitter)

        self.exec_btn = QPushButton("Execute Plan")
        self.exec_btn.setObjectName("btnSend")
        self.exec_btn.setVisible(False)
        self.exec_btn.clicked.connect(self.on_execute_plan)
        layout.addWidget(self.exec_btn)

        self.input_edit.setFocus()

    def eventFilter(self, obj, event):
        if obj == self.input_edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Return and not (event.modifiers() & Qt.ShiftModifier):
                self.on_send()
                return True
            if event.key() == Qt.Key_Up and not self.input_edit.toPlainText():
                self._history_up()
                return True
            if event.key() == Qt.Key_Down and not self.input_edit.toPlainText():
                self._history_down()
                return True
        return super().eventFilter(obj, event)

    def _history_up(self):
        if not self._input_history:
            return
        if self._history_index < len(self._input_history) - 1:
            self._history_index += 1
            self.input_edit.setPlainText(self._input_history[-(self._history_index + 1)])
            self.input_edit.moveCursor(self.input_edit.textCursor().End)

    def _history_down(self):
        if self._history_index >= 0:
            self._history_index -= 1
        if self._history_index < 0:
            self.input_edit.clear()
        else:
            self.input_edit.setPlainText(self._input_history[-(self._history_index + 1)])
            self.input_edit.moveCursor(self.input_edit.textCursor().End)

    def _log(self, msg, style=""):
        ts = datetime.now().strftime("%H:%M:%S")
        if style:
            self.output_edit.append(f'<span style="color:{style};font-size:10pt">[{ts}] {msg}</span>')
        else:
            self.output_edit.append(f'<span style="font-size:10pt">[{ts}] {msg}</span>')
        self._scroll_bottom()

    def _scroll_bottom(self):
        sb = self.output_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def _start_loading_animation(self, base_text):
        self._loading_dots = 0
        self._loading_base = base_text
        if self._loading_timer:
            self._loading_timer.stop()
        self._loading_timer = QTimer()
        self._loading_timer.timeout.connect(self._update_loading)
        self._loading_timer.start(500)

    def _update_loading(self):
        self._loading_dots = (self._loading_dots + 1) % 4
        dots = "." * self._loading_dots
        self.status_label.setText(f"{self._loading_base}{dots}")

    def _stop_loading_animation(self):
        if self._loading_timer:
            self._loading_timer.stop()
            self._loading_timer = None

    def on_send(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self._input_history.append(text)
        self._history_index = -1
        self.input_edit.clear()
        self._start_llm(text)

    def _get_context_string(self):
        result = self.plugin.registry.execute("get_project_info", {}, None)
        if result.get("status") == "ok":
            layers = result.get("layers", [])
            if layers:
                lines = ["Loaded layers:"]
                for l in layers:
                    lines.append(f"  - {l['name']} ({l['type']}, {l.get('feature_count', 'N/A')} features)")
                return "\n".join(lines)
        return "No layers loaded."

    def _update_context(self):
        self._real_context = self._get_context_string()

    def _replan_remaining_steps(self, done_idx):
        remaining = self._execution_steps[done_idx + 1:]
        if not remaining:
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(50, self._execute_next_step)
            return
        context = getattr(self, '_real_context', self._get_context_string())
        if "No layers loaded" in context:
            from qgis.PyQt.QtCore import QTimer
            QTimer.singleShot(50, self._execute_next_step)
            return

        self.output_edit.append(f'  <span style="color:#1565c0">[Re-plan] Context mis à jour — {len(remaining)} étapes restantes à re-planifier...</span>')
        self.status_label.setText("Re-planning with real context...")
        from qgis.PyQt.QtCore import QCoreApplication
        QCoreApplication.processEvents()

        user_text = getattr(self, '_last_user_text', '')
        done_tools = [s.get("tool", "") for s in self._execution_steps[:done_idx + 1]]
        done_summary = "Already executed: " + ", ".join(done_tools)
        tool_descs = "\n".join(
            f"  - {n}: {d}" for n, d in self.plugin.registry.get_tools_with_descriptions()
        )
        prompt = (
            f"You are a QGIS automation engine.\n\n"
            f"Project context (REAL loaded layers):\n{context}\n\n"
            f"{done_summary}\n\n"
            f"Remaining task: {user_text}\n\n"
            f"Available tools:\n{tool_descs}\n\n"
            f"CRITICAL: Use the EXACT layer names from the context above.\n"
            f"Generate the remaining steps as JSON plan {{\"steps\": [...]}}.\n"
            f"Output ONLY the JSON."
        )

        try:
            resp = self.plugin.llm_client.chat_planner(
                "Generate JSON plan for remaining QGIS steps using real layer context.",
                prompt
            )
            new_plan, err = self.plugin.parser.parse_llm_response(resp)
            if err or not new_plan:
                self.output_edit.append(f'  <span style="color:#c62828">[Re-plan] Parse error: {err} — continuing with original plan</span>')
                from qgis.PyQt.QtCore import QTimer
                QTimer.singleShot(50, self._execute_next_step)
                return
            valid, schema_err = self.plugin.validator.validate_plan_schema(new_plan)
            if not valid:
                self.output_edit.append(f'  <span style="color:#c62828">[Re-plan] Schema error: {schema_err} — continuing with original plan</span>')
                from qgis.PyQt.QtCore import QTimer
                QTimer.singleShot(50, self._execute_next_step)
                return
            new_steps = new_plan.get("steps", [])
            if new_steps:
                self.output_edit.append(f'  <span style="color:#1565c0">[Re-plan] {len(new_steps)} étapes générées avec les vrais noms de couches</span>')
                self._execution_steps = self._execution_steps[:done_idx + 1] + new_steps
        except Exception as e:
            self.output_edit.append(f'  <span style="color:#c62828">[Re-plan] Error: {e} — continuing with original plan</span>')
        from qgis.PyQt.QtCore import QTimer
        QTimer.singleShot(50, self._execute_next_step)

    def _start_llm(self, text):
        self._last_user_text = text
        self.send_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self.exec_btn.setVisible(False)
        self.plan_edit.setVisible(False)
        self._pending_plan = None
        self._executing = False
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat("Gathering context...")
        self.status_label.setText("")
        self.output_edit.append(f'<span style="color:#444;font-weight:bold">[{datetime.now():%H:%M:%S}] >>> {text[:200]}</span>')
        self._scroll_bottom()

        self._start_loading_animation("LLM en cours d'analyse")

        context_str = self._get_context_string()
        self._real_context = context_str

        self.progress.setValue(5)
        self.progress.setFormat("Contacting LLM...")

        self._worker = LlmWorker(self.plugin, text, context_str)
        self._worker.sig.step.connect(self._on_worker_step)
        self._worker.sig.parsed.connect(self._on_plan_ready)
        self._worker.sig.fail.connect(self._on_worker_fail)
        self._worker.start()

    def _on_worker_step(self, pct, msg):
        self.progress.setValue(pct)
        self.progress.setFormat(msg)
        self.status_label.setText(msg)

    def _on_plan_ready(self, plan):
        self._stop_loading_animation()
        import json
        self._pending_plan = self._refine_plan(self._verify_paths(plan))
        steps = self._pending_plan.get("steps", [])
        if not steps:
            self.output_edit.append(f'<span style="color:#888">[{datetime.now():%H:%M:%S}] No actions to execute</span>')
            self.status_label.setText("No actions to execute")
            self.progress.setVisible(False)
            self.send_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
            self.plan_edit.setVisible(False)
            return
        self.output_edit.append(f'<span style="color:#1565C0;font-weight:bold">[{datetime.now():%H:%M:%S}] Plan generated: {len(steps)} step(s)</span>')
        for i, s in enumerate(steps):
            self.output_edit.append(f'  <span style="color:#555">Step {i+1}: <b>{s["tool"]}</b></span>')

        self.plan_edit.setText(json.dumps(plan, indent=2, ensure_ascii=False))
        self.plan_edit.setVisible(True)

        if self.preview_cb.isChecked():
            self.exec_btn.setVisible(True)
            self.progress.setValue(100)
            self.progress.setFormat("Preview mode")
            self.status_label.setText("Review plan and click 'Execute Plan' to run")
            self.send_btn.setEnabled(True)
            self.clear_btn.setEnabled(True)
        else:
            self._execute_plan(plan)

    def _on_worker_fail(self, msg):
        self._stop_loading_animation()
        self.progress.setVisible(False)
        self.progress.setFormat("Failed")
        self.status_label.setText(f"<span style='color:#c62828'>Error: {msg[:200]}</span>")
        self.output_edit.append(f'<span style="color:#c62828;font-weight:bold">[{datetime.now():%H:%M:%S}] ERROR: {msg}</span>')
        self._scroll_bottom()
        self.send_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    def on_execute_plan(self):
        if not self._pending_plan:
            return
        self.exec_btn.setVisible(False)
        self.plan_edit.setVisible(False)
        self.send_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)
        self._execute_plan(self._pending_plan)

    def _execute_plan(self, plan):
        self._executing = True
        self._execution_steps = plan.get("steps", [])
        self._execution_results = []
        self._execution_index = 0
        total = len(self._execution_steps)
        self.output_edit.append(f'<span style="color:#1565C0;font-weight:bold">[{datetime.now():%H:%M:%S}] Executing {total} step(s)...</span>')
        self.progress.setValue(0)
        self.progress.setFormat(f"Step 1/{total}")
        self.status_label.setText("Executing...")
        self.send_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        QTimer.singleShot(50, self._execute_next_step)

    def _execute_next_step(self):
        if not self._executing:
            return

        idx = self._execution_index
        steps = self._execution_steps

        if idx >= len(steps):
            self._finish_execution()
            return

        step = steps[idx]
        tool_name = step.get("tool", "")
        parameters = step.get("parameters", {})

        total = len(steps)
        pct = int(((idx + 1) / total) * 100)
        self.progress.setValue(pct)
        self.progress.setFormat(f"Step {idx+1}/{total}: {tool_name} ({pct}%)")
        self.status_label.setText(f"[{datetime.now():%H:%M:%S}] Executing: {tool_name}")
        self.output_edit.append(f'  <span style="color:#555">[{idx+1}/{total}] <b>{tool_name}</b>...</span>')

        import time
        from qgis.PyQt.QtCore import QCoreApplication
        start = time.time()
        QCoreApplication.processEvents()
        result = self.plugin.registry.execute(tool_name, parameters)
        QCoreApplication.processEvents()
        elapsed = time.time() - start

        entry = {
            "step": idx + 1,
            "tool": tool_name,
            "parameters": parameters,
            "result": result,
            "elapsed_s": round(elapsed, 2),
        }
        self._execution_results.append(entry)
        self.plugin.logger.info(f"Step {idx+1}/{total}: {tool_name} -> {result.get('status')} ({elapsed:.2f}s)")

        if result.get("status") == "error":
            msg = result.get("message", "Unknown error")
            self.output_edit.append(f'    <span style="color:#c62828">FAILED: {msg}</span>')
            self._fail_execution(msg)
            return

        self.output_edit.append(f'    <span style="color:#2e7d32">OK</span> <span style="color:#888">({elapsed:.1f}s): {result.get("message", "")}</span>')

        self._execution_index += 1

        if tool_name in self.STATE_CHANGING_TOOLS:
            self._update_context()
            QTimer.singleShot(100, lambda: self._replan_remaining_steps(self._execution_index - 1))
            return

        QTimer.singleShot(50, self._execute_next_step)

    def _finish_execution(self):
        self._executing = False
        self._fixer_retries = 0
        self._clear_choice_buttons()
        self.progress.setValue(100)
        self.progress.setFormat("Complete!")
        n = len(self._execution_results)
        ok = sum(1 for r in self._execution_results if r.get("result", {}).get("status") == "ok")
        self.status_label.setText(f"Complete: {ok}/{n} steps succeeded")
        color = "#2e7d32" if ok == n else "#e65100"
        self.output_edit.append(f'<span style="color:{color};font-weight:bold">[{datetime.now():%H:%M:%S}] Execution complete ({ok}/{n})</span>')
        self._scroll_bottom()
        self.send_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self._pending_plan = None
        QTimer.singleShot(3000, lambda: self.progress.setVisible(False))

    def _fail_execution(self, msg):
        self._executing = False
        failed_idx = self._execution_index
        step = self._execution_steps[failed_idx] if failed_idx < len(self._execution_steps) else {}
        tool_name = step.get("tool", "") if isinstance(step, dict) else ""
        err = self.plugin.registry._classify_error(msg, tool_name, step.get("parameters", {}))
        suggestion = err.get("suggestion", "")

        if suggestion:
            self.output_edit.append(f"    Suggestion: {suggestion}")

        if self._fixer_retries >= self.MAX_FIXER_RETRIES or not self._pending_plan or failed_idx >= len(self._pending_plan.get("steps", [])):
            self._finalize_fail(msg)
            return

        self._fixer_retries += 1
        self.output_edit.append(f"[{datetime.now():%H:%M:%S}] Fixer LLM attempt {self._fixer_retries}/{self.MAX_FIXER_RETRIES}...")
        self.status_label.setText("Fixer LLM: correcting plan...")
        self.progress.setFormat(f"Fixer {self._fixer_retries}/{self.MAX_FIXER_RETRIES}")
        self.progress.setVisible(True)

        if self._fixer_retries == 1:
            QTimer.singleShot(100, lambda: self._ask_user_for_choices(failed_idx, msg))
        else:
            QTimer.singleShot(100, lambda: self._try_fixer(failed_idx, msg))

    def _try_fixer(self, failed_idx, error_msg):
        steps = self._pending_plan.get("steps", [])
        failed_step = steps[failed_idx] if failed_idx < len(steps) else {}
        tool_descs = "\n".join(
            f"  - {n}: {d}" for n, d in self.plugin.registry.get_tools_with_descriptions()
        )
        context = getattr(self, '_real_context', self._get_context_string())
        prompt = FIXER_PROMPT_UI.format(
            tool_descriptions=tool_descs,
            plan_json=json.dumps(self._pending_plan, ensure_ascii=False),
            step_idx=failed_idx + 1,
            failed_tool=failed_step.get("tool", "?"),
            failed_params=json.dumps(failed_step.get("parameters", {}), ensure_ascii=False),
            error_message=error_msg,
            real_context=context,
        )

        try:
            resp = self.plugin.llm_client.chat_fixer(
                "You are a QGIS error recovery system. Generate and return ONLY the corrected JSON plan. No text before or after.",
                prompt
            )
            new_plan, err = self.plugin.parser.parse_llm_response(resp)
            if err or not new_plan:
                self.output_edit.append(f"[{datetime.now():%H:%M:%S}] Fixer LLM returned invalid JSON: {err}")
                self._fail_execution(f"Fixer failed to parse: {err}")
                return
            valid, schema_err = self.plugin.validator.validate_plan_schema(new_plan)
            if not valid:
                self.output_edit.append(f"[{datetime.now():%H:%M:%S}] Fixer LLM produced invalid schema: {schema_err}")
                self._fail_execution(f"Fixer schema invalid: {schema_err}")
                return

            self.output_edit.append(f"[{datetime.now():%H:%M:%S}] Fixer LLM generated corrected plan ({len(new_plan.get('steps',[]))} steps) - re-executing...")
            self._pending_plan = new_plan
            self._execute_plan(new_plan)
        except Exception as e:
            self._fail_execution(f"Fixer LLM error: {e}")

    def _ask_user_for_choices(self, failed_idx, error_msg):
        steps = self._pending_plan.get("steps", [])
        failed_step = steps[failed_idx] if failed_idx < len(steps) else {}
        tool_descs = "\n".join(
            f"  - {n}: {d}" for n, d in self.plugin.registry.get_tools_with_descriptions()
        )
        user_query = getattr(self, '_last_user_text', '')
        context = getattr(self, '_real_context', self._get_context_string())
        prompt = SOLVER_PROMPT.format(
            step_idx=failed_idx + 1,
            failed_tool=failed_step.get("tool", "?"),
            failed_params=json.dumps(failed_step.get("parameters", {}), ensure_ascii=False),
            error_message=error_msg,
            user_query=user_query,
            tool_descriptions=tool_descs,
            real_context=context,
        )

        try:
            resp = self.plugin.llm_client.chat_fixer(
                "Tu es un assistant qui propose des solutions de correction pour QGIS. Réponds UNIQUEMENT avec le JSON demandé.",
                prompt
            )
            parsed, err = self.plugin.parser.parse_llm_response(resp)
            if err or not parsed or "solutions" not in parsed or not parsed["solutions"]:
                self._try_fixer(failed_idx, error_msg)
                return

            self._paused_at_step = failed_idx
            self._paused_error_msg = error_msg
            self._solutions = parsed["solutions"]
            self._show_choices(parsed["solutions"])
        except Exception as e:
            self._try_fixer(failed_idx, error_msg)

    def _show_choices(self, solutions):
        self._clear_choice_buttons()
        self.choices_label.setText(
            f"<span style='color:#c62828'><b>Échec à l'étape {self._paused_at_step + 1} :</b></span> "
            f"{self._paused_error_msg[:120]}<br>"
            f"<i>Choisis une solution :</i>"
        )
        for i, sol in enumerate(solutions):
            btn = QPushButton(f"{i + 1}. {sol.get('label', f'Option {i+1}')}")
            btn.setToolTip(sol.get('description', ''))
            btn.clicked.connect(lambda checked, idx=i: self._apply_choice(idx))
            self._choice_buttons.append(btn)
            self.choices_btn_layout.addWidget(btn)

        cancel_btn = QPushButton("Auto-fix")
        cancel_btn.setObjectName("btnClear")
        cancel_btn.setToolTip("Laisser le LLM corriger automatiquement")
        cancel_btn.clicked.connect(lambda: self._fallback_to_fixer())
        self._choice_buttons.append(cancel_btn)
        self.choices_btn_layout.addWidget(cancel_btn)

        self.choices_container.setVisible(True)

    def _apply_choice(self, idx):
        self._clear_choice_buttons()
        sol = self._solutions[idx]
        action = sol.get("action")

        if action is None:
            self.output_edit.append(f"[{datetime.now():%H:%M:%S}] Choix utilisateur: ignorer l'étape")
            self._execution_index = self._paused_at_step + 1
            self._executing = True
            QTimer.singleShot(50, self._execute_next_step)
            return

        self.output_edit.append(
            f"[{datetime.now():%H:%M:%S}] Choix utilisateur: {sol.get('label', 'Solution')} - "
            f"{sol.get('description', '')}"
        )
        step = self._pending_plan["steps"][self._paused_at_step]
        step["tool"] = action["tool"]
        step["parameters"] = action.get("parameters", {})
        self._pending_plan["steps"][self._paused_at_step] = step
        self._execution_steps = self._pending_plan["steps"]
        self._execution_index = self._paused_at_step
        self._executing = True
        QTimer.singleShot(50, self._execute_next_step)

    def _clear_choice_buttons(self):
        for btn in self._choice_buttons:
            self.choices_btn_layout.removeWidget(btn)
            btn.deleteLater()
        self._choice_buttons = []
        self.choices_container.setVisible(False)

    def _fallback_to_fixer(self):
        self._clear_choice_buttons()
        QTimer.singleShot(100, lambda: self._try_fixer(self._paused_at_step, self._paused_error_msg))

    def _extract_paths(self, text):
        raw = re.findall(
            r'[A-Za-z]:[\\/][^"\' \t\n<>|]+',
            text
        )
        result = []
        for p in raw:
            p = p.rstrip(',;.:!?)')
            if re.search(r'\.[a-zA-Z0-9]{2,4}$', p) or re.fullmatch(r'[A-Za-z]:[\\/].+', p):
                result.append(p)
        return result

    def _verify_paths(self, plan):
        if not hasattr(self, '_last_user_text') or not self._last_user_text:
            return plan
        user_paths = self._extract_paths(self._last_user_text)
        if not user_paths:
            return plan

        steps = plan.get("steps", [])
        modified = False

        for step in steps:
            params = step.get("parameters", {})
            for key, val in list(params.items()):
                if not isinstance(val, str) or not re.match(r'[A-Za-z]:[\\/]', val):
                    continue
                plan_norm = val.lower().replace('/', '\\')
                for up in user_paths:
                    up_norm = up.lower().replace('/', '\\')
                    if plan_norm == up_norm:
                        break
                    if abs(len(plan_norm) - len(up_norm)) > 5:
                        continue
                    matches = sum(1 for a, b in zip(plan_norm, up_norm) if a == b)
                    similarity = matches / max(len(plan_norm), len(up_norm))
                    if similarity > 0.8:
                        params[key] = up
                        modified = True
                        self.output_edit.append(
                            f"[{datetime.now():%H:%M:%S}] Chemin corrigé: '{val}' -> '{up}' "
                            f"(hallucination LLM)"
                        )
                        break

        if modified:
            self.plugin.logger.info(
                f"Path hallucination fix applied: {sum(1 for s in steps for k, v in s.get('parameters', {}).items() if isinstance(v, str) and v != plan.get('steps', [{}])[0].get('parameters', {}).get(k))} paths corrected"
            )
        return plan

    def _refine_plan(self, plan):
        steps = plan.get("steps", [])
        if not steps or not hasattr(self, '_last_user_text'):
            return plan
        user_lower = self._last_user_text.lower()
        modified = False

        # 1. Remove contradictory create_project when followed by open_project
        if any(s["tool"] == "open_project" for s in steps):
            steps = [s for s in steps if s["tool"] != "create_project"]
            modified = True

        # 2. Ensure calculate_field is used when user asks for surface/area calculations
        calc_keywords = ["surface", "hectare", "area", "calcule", "$area", "$length", "$perimeter"]
        if any(kw in user_lower for kw in calc_keywords):
            has_calc = any(s["tool"] == "calculate_field" for s in steps)
            if not has_calc:
                for i, s in enumerate(steps):
                    if s["tool"] == "run_algorithm":
                        algo = s.get("parameters", {}).get("algorithm", "")
                        algo_params = s.get("parameters", {}).get("parameters", {})
                        if any(kw in algo.lower() for kw in ["field", "calc", "autoinc"]):
                            layer = algo_params.get("INPUT", "")
                            field_name = algo_params.get("FIELD_NAME", "surface_ha")
                            steps[i] = {
                                "tool": "calculate_field",
                                "parameters": {
                                    "layer": layer,
                                    "field_name": field_name,
                                    "expression": "$area / 10000",
                                    "field_type": 6
                                }
                            }
                            modified = True

        # 3. Ensure export_layer is used when user asks for exports
        export_keywords = ["export", "geojson", "gpkg", "shapefile"]
        if any(kw in user_lower for kw in export_keywords):
            has_export = any(s["tool"] in ("export_layer", "import_layer") for s in steps)
            if not has_export:
                for i, s in enumerate(steps):
                    if s["tool"] == "run_algorithm":
                        algo = s.get("parameters", {}).get("algorithm", "")
                        algo_params = s.get("parameters", {}).get("parameters", {})
                        if any(kw in algo.lower() for kw in ["export", "save", "convert"]):
                            layer = algo_params.get("INPUT", "")
                            output = algo_params.get("OUTPUT", "D:/export.geojson")
                            steps[i] = {
                                "tool": "export_layer",
                                "parameters": {
                                    "layer": layer,
                                    "output_path": output,
                                    "format": output.split(".")[-1] if "." in output else "geojson"
                                }
                            }
                            modified = True

        if modified:
            plan["steps"] = steps
            self.output_edit.append(f"[{datetime.now():%H:%M:%S}] Plan corrigé ({len(steps)} étapes)")
        return plan

    def _finalize_fail(self, msg):
        self._executing = False
        self._fixer_retries = 0
        self._clear_choice_buttons()
        self.progress.setVisible(False)
        self.status_label.setText(f"<span style='color:#c62828'>Failed: {msg[:200]}</span>")
        self.output_edit.append(f'<span style="color:#c62828;font-weight:bold">[{datetime.now():%H:%M:%S}] ERROR: {msg}</span>')
        self._scroll_bottom()
        self.send_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self._pending_plan = None

    def on_settings(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.plugin, self)
        dlg.exec_()

    def on_clear(self):
        self._clear_choice_buttons()
        self.output_edit.clear()
        self.plan_edit.clear()
        self.plan_edit.setVisible(False)
        self.exec_btn.setVisible(False)
        self.status_label.setText("Ready")
        self.progress.setVisible(False)
        self.input_edit.clear()
