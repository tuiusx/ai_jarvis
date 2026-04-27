import statistics
import sys
import time
from pathlib import Path
import logging

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.agent import Agent

logging.getLogger().setLevel(logging.CRITICAL)


class _BenchMemory:
    def __init__(self):
        self.data = []

    def recall(self, perception):
        return ""

    def store(self, experience):
        self.data.append(experience)

    def get_context(self):
        return ""


class _BenchLongMemory:
    def __init__(self):
        self.data = []
        self.semantic_top_k = 2
        self.semantic_response_k = 2

    def add(self, text):
        self.data.append({"text": text})

    def search(self, query, limit=2):
        return [item for item in self.data if query in item.get("text", "")][:limit]


class _BenchLLM:
    def think(self, perception, context):
        content = str(perception.get("content", "")).lower()
        if "status" in content:
            return {"intent": "status", "response": "status"}
        if content.startswith("lembre"):
            return {"intent": "remember", "memory": content.replace("lembre ", "", 1), "response": "ok", "needs_action": True}
        return {"intent": "home_control", "device": "luz", "action": "on", "response": "ligando", "needs_action": True}


class _BenchPlanner:
    def create_plan(self, analysis):
        if analysis.get("intent") == "status":
            return {"steps": [{"action": "status"}]}
        if analysis.get("intent") == "remember":
            return {"steps": [{"action": "remember", "text": analysis.get("memory", "")}]}
        return {"steps": [{"tool": "home_control", "device": "luz", "action": "on"}]}


class _BenchTools:
    def execute(self, step):
        if step.get("tool") == "home_control":
            return {"message": "ok"}
        return {"message": "noop"}


def run_benchmark(iterations=300):
    agent = Agent(
        llm=_BenchLLM(),
        memory=_BenchMemory(),
        long_memory=_BenchLongMemory(),
        planner=_BenchPlanner(),
        tools=_BenchTools(),
        interface=None,
        performance_config={
            "enabled_metrics": True,
            "slow_command_threshold_ms": 10_000,
            "lazy_init_enabled": True,
        },
    )
    commands = [
        "ligar a luz da casa",
        "status",
        "lembre mercado amanha",
        "ligar a luz da casa",
        "status",
    ]
    samples = []
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    for index in range(iterations):
        content = commands[index % len(commands)]
        started = time.perf_counter()
        payload = agent.process_command_data(
            data={"mode": "text", "content": content, "confidence": 1.0},
            auto_remember=True,
        )
        if payload.get("state") == "processed":
            samples.append((time.perf_counter() - started) * 1000.0)
    wall_elapsed = time.perf_counter() - wall_start
    cpu_elapsed = time.process_time() - cpu_start

    if not samples:
        print("Nenhum comando processado.")
        return

    p95_index = max(0, int(round(0.95 * (len(samples) - 1))))
    p95 = sorted(samples)[p95_index]
    print(f"Comandos processados: {len(samples)}")
    print(f"Tempo medio por comando (ms): {statistics.mean(samples):.3f}")
    print(f"P95 por comando (ms): {p95:.3f}")
    print(f"Tempo total de parede (s): {wall_elapsed:.3f}")
    print(f"CPU process time total (s): {cpu_elapsed:.3f}")
    print(f"CPU process time por comando (ms): {(cpu_elapsed / len(samples)) * 1000.0:.3f}")


if __name__ == "__main__":
    run_benchmark()
