import logging
import time

logging.basicConfig(level=logging.INFO)


class Agent:
    def __init__(
        self,
        llm,
        memory,
        planner,
        tools,
        interface,
        long_memory=None,
        rate_limiter=None,
        audit_logger=None,
        app_mode: str = "dev",
    ):
        self.llm = llm
        self.memory = memory
        self.long_memory = long_memory
        self.planner = planner
        self.tools = tools
        self.interface = interface
        self.rate_limiter = rate_limiter
        self.audit = audit_logger
        self.app_mode = app_mode
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

        if self.rate_limiter is not None:
            allowed, wait_seconds = self.rate_limiter.allow()
            if not allowed:
                if self.interface is not None:
                    self.interface.output(f"Comando ignorado para evitar spam. Aguarde {wait_seconds:.2f}s.")
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
        if self.audit:
            self.audit.log("agent.perception", mode=mode, content=content, confidence=confidence)
        return perception

    def analyze(self, perception):
        context = self.memory.recall(perception)
        analysis = self.llm.think(perception=perception, context=context)
        logging.info("Analise concluida")
        if self.audit:
            self.audit.log("agent.analysis", intent=analysis.get("intent", "unknown"))
        return analysis

    def plan(self, analysis):
        if not analysis:
            return None

        plan = self.planner.create_plan(analysis)
        if not isinstance(plan, dict) or "steps" not in plan:
            logging.warning("Plano invalido")
            return None

        logging.info("Plano criado (%s passos)", len(plan["steps"]))
        if self.audit:
            self.audit.log("agent.plan", steps=len(plan["steps"]))
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
                        if self.audit:
                            self.audit.log("memory.remember", text=text)
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
                            if self.audit:
                                self.audit.log("memory.recall", query=query, matches=len(matches))
                        else:
                            results.append({"message": f"Nao encontrei nada salvo sobre '{query}'."})
                            if self.audit:
                                self.audit.log("memory.recall", query=query, matches=0)
                    continue

                tool_result = self.tools.execute(step)
                results.append(tool_result)
                if self.audit and isinstance(step, dict):
                    event_name = step.get("tool") or step.get("action") or "unknown"
                    severity = "error" if isinstance(tool_result, dict) and "error" in tool_result else "info"
                    self.audit.log("tool.execute", severity=severity, tool=event_name, result=tool_result)
            except Exception as exc:
                logging.error("Erro no passo %s", step)
                results.append({"error": str(exc), "step": step})
                if self.audit:
                    self.audit.log("tool.execute", severity="error", tool=str(step), error=str(exc))

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
        if self.audit:
            self.audit.log("agent.experience_saved")

    def run(self):
        self.interface.output(f"JARVIS online ({self.app_mode}). Sempre escutando...")

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
        if self.audit:
            self.audit.log("agent.stop")
