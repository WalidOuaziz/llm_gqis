import time
from datetime import datetime


class ExecutionEngine:
    def __init__(self, registry, logger):
        self.registry = registry
        self.logger = logger
        self.execution_history = []

    def execute_plan(self, plan, on_step=None, context=None):
        steps = plan.get("steps", [])
        results = []
        total = len(steps)

        self.logger.info(f"Starting execution of {total} step(s)")

        for i, step in enumerate(steps):
            tool_name = step.get("tool", "")
            parameters = step.get("parameters", {})
            step_index = i + 1

            if on_step:
                on_step(step_index, total, tool_name, parameters)

            self.logger.info(f"Step {step_index}/{total}: {tool_name} {parameters}")

            start = time.time()
            result = self.registry.execute(tool_name, parameters, context)
            elapsed = time.time() - start

            entry = {
                "step": step_index,
                "tool": tool_name,
                "parameters": parameters,
                "result": result,
                "elapsed_s": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
            }
            self.execution_history.append(entry)
            results.append(entry)

            if result.get("status") == "error":
                self.logger.error(f"Step {step_index} failed: {result.get('message')}")
                if on_step:
                    on_step(step_index, total, tool_name, parameters, error=result.get("message"))
                return {
                    "status": "error",
                    "step_failed": step_index,
                    "message": result.get("message"),
                    "results": results,
                }

            self.logger.info(f"Step {step_index} completed in {elapsed:.2f}s")

        self.logger.info("All steps completed successfully")
        return {"status": "ok", "results": results}

    def get_history(self, n=10):
        return self.execution_history[-n:]
