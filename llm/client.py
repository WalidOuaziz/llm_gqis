import json
import urllib.request
import urllib.error
import ssl


OLLAMA_PATHS = ("/api/chat", "/api/generate")


class ModelConfig:
    def __init__(self, config_dict):
        self.endpoint = config_dict.get("endpoint", "http://localhost:11434/api/chat")
        self.model = config_dict.get("model", "qwen2.5:3b")
        self.api_key = config_dict.get("api_key", "")
        self.timeout = config_dict.get("timeout", 120)
        self.temperature = config_dict.get("temperature", 0.1)
        self.max_tokens = config_dict.get("max_tokens", 4000)

    def _is_ollama(self):
        ep = self.endpoint.lower().rstrip("/")
        return any(ep.endswith(p) for p in OLLAMA_PATHS) or "11434" in ep

    def _needs_auth(self):
        return bool(self.api_key) and not self._is_ollama()


class LlmClient:
    def __init__(self, config):
        self.planner = ModelConfig({
            "endpoint": config.get("endpoint", "http://localhost:11434/api/chat"),
            "model": config.get("model", "qwen2.5:3b"),
            "api_key": config.get("api_key", ""),
            "timeout": config.get("timeout", 120),
            "temperature": config.get("planner_temperature", config.get("temperature", 0.3)),
            "max_tokens": config.get("max_tokens", 4000),
        })
        self.fixer = ModelConfig({
            "endpoint": config.get("fixer_endpoint", config.get("endpoint", "http://localhost:11434/api/chat")),
            "model": config.get("fixer_model", config.get("model", "qwen2.5:3b")),
            "api_key": config.get("fixer_api_key", config.get("api_key", "")),
            "timeout": config.get("timeout", 120),
            "temperature": config.get("fixer_temperature", 0.1),
            "max_tokens": config.get("max_tokens", 4000),
        })

    def _send(self, model_cfg, messages):
        if model_cfg._is_ollama():
            body = {
                "model": model_cfg.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": model_cfg.temperature,
                    "num_predict": model_cfg.max_tokens,
                },
            }
        else:
            body = {
                "model": model_cfg.model,
                "messages": messages,
                "temperature": model_cfg.temperature,
                "max_tokens": model_cfg.max_tokens,
            }

        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "QGIS-LLM-Agent/1.0",
        }
        if model_cfg._needs_auth():
            headers["Authorization"] = f"Bearer {model_cfg.api_key}"

        ctx = None
        if model_cfg._is_ollama() and "localhost" in model_cfg.endpoint:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            req = urllib.request.Request(model_cfg.endpoint, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=model_cfg.timeout, context=ctx) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API HTTP {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"LLM API connection failed: {e.reason}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM returned invalid JSON: {e}")

    def _extract_content(self, response):
        if "message" in response and "content" in response["message"]:
            return response["message"]["content"].strip()
        elif "choices" in response and len(response["choices"]) > 0:
            return response["choices"][0].get("message", {}).get("content", "").strip()
        elif "response" in response:
            return response["response"].strip()
        raise RuntimeError(f"Unexpected LLM response: {json.dumps(response)[:500]}")

    def chat_planner(self, system_prompt, user_message):
        resp = self._send(self.planner, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ])
        return self._extract_content(resp)

    def chat_fixer(self, system_prompt, error_context):
        resp = self._send(self.fixer, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": error_context},
        ])
        return self._extract_content(resp)
