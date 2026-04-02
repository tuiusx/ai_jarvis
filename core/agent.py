import logging
import time

logging.basicConfig(level=logging.INFO)


class Agent:
    def __init__(self, llm, memory, planner, tools, interface, long_memory=None):
        self.llm = llm
        self.memory = memory
        self.long_memory = long_memory
        self.planner = planner
        self.tools = tools
        self.interface = interface
        self.running = True

    def perceive(self):
        if self.interface is None:
            return None

        data = self.interface.get_input()
        if not data:
            return None

        if not isinstance(data, dict):
            data = {"mode": "text", "content": str(data), "confidence": 1.0}

        content = data.get("content", "").strip()
        mode = data.get("mode", "unknown")
        confidence = data.get("confidence", 1.0)

        if not content:
            return None

        if content.lower() in ["sair", "exit", "quit"]:
            self.stop()
            self.interface.output("Encerrando JARVIS...")
            return None

        perception = {
            "type": mode,
            "content": content,
            "confidence": confidence,
            "timestamp": time.time(),
        }

        logging.info("Percepcao [%s]: %s", mode, content)
        return perception

    def analyze(self, perception):
        context = self.memory.recall(perception)
        analysis = self.llm.think(perception=perception, context=context)
        logging.info("Analise concluida")
        return analysis

    def plan(self, analysis):
        if not analysis:
            return None

        plan = self.planner.create_plan(analysis)
        if not isinstance(plan, dict) or "steps" not in plan:
            logging.warning("Plano invalido")
            return None

        logging.info("Plano criado (%s passos)", len(plan["steps"]))
        return plan

    def act(self, plan):
        results = []
        if not plan:
            return results

        for step in plan["steps"]:
            try:
                if isinstance(step, dict) and step.get("action") == "remember":
                    text = step.get("text", "")
                    if self.long_memory is None:
                        results.append({"error": "Memoria de longo prazo nao configurada."})
                    else:
                        self.long_memory.add(text)
                        results.append({"message": f"Memoria registrada: {text}"})
                    continue

                if isinstance(step, dict) and step.get("action") == "recall":
                    query = step.get("query", "")
                    limit = step.get("limit", 2)
                    if self.long_memory is None:
                        results.append({"error": "Memoria de longo prazo nao configurada."})
                    else:
                        matches = self.long_memory.search(query, limit=limit)
                        if matches:
                            summary = "; ".join(item.get("text", "") for item in matches)
                            results.append({"message": f"Encontrei na memoria: {summary}"})
                        else:
                            results.append({"message": f"Nao encontrei nada salvo sobre '{query}'."})
                    continue

                results.append(self.tools.execute(step))
            except Exception as exc:
                logging.error("Erro no passo %s", step)
                results.append({"error": str(exc), "step": step})

        return results

    def remember(self, perception, analysis, plan, results):
        experience = {
            "perception": perception,
            "analysis": analysis,
            "plan": plan,
            "results": results,
            "timestamp": time.time(),
        }
        self.memory.store(experience)
        logging.info("Experiencia salva")

    def run(self):
        self.interface.output("JARVIS online. Sempre escutando...")

        while self.running:
            perception = self.perceive()
            if not perception:
                time.sleep(0.05)
                continue

            analysis = self.analyze(perception)
            plan = self.plan(analysis)
            results = self.act(plan)

            for result in results:
                if isinstance(result, dict):
                    if "message" in result:
                        self.interface.output(result["message"])
                    elif "error" in result:
                        self.interface.output(f"Erro: {result['error']}")

            try:
                self.remember(perception, analysis, plan, results)
            except Exception as exc:
                logging.error("Falha ao gravar memoria: %s", exc)

    def stop(self):
        self.running = False
        logging.info("Agente desligado")
