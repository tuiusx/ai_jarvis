import logging
import os
import time
import uuid

from core.command_pipeline import CommandFlowPipeline, CommandPrecheckPipeline

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
        retention_summary: dict | None = None,
        access_controller=None,
        network_guard=None,
        performance_config=None,
        critical_confirmation_enabled: bool = True,
        critical_confirmation_ttl_seconds: int = 90,
        critical_confirmation_pin_env: str = "JARVIS_ADMIN_PIN",
        critical_confirmation_require_pin: bool = True,
        tool_retry_attempts: int = 1,
        tool_retry_backoff_seconds: float = 0.2,
        system_monitor=None,
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
        self.access_controller = access_controller
        self.network_guard = network_guard
        self.performance_config = dict(performance_config or {})
        self.running = True
        self.critical_confirmation_enabled = bool(critical_confirmation_enabled)
        self.critical_confirmation_ttl_seconds = max(15, int(critical_confirmation_ttl_seconds))
        self.critical_confirmation_pin_env = str(critical_confirmation_pin_env or "JARVIS_ADMIN_PIN")
        self.critical_confirmation_require_pin = bool(critical_confirmation_require_pin)
        self.tool_retry_attempts = max(0, int(tool_retry_attempts))
        self.tool_retry_backoff_seconds = max(0.0, float(tool_retry_backoff_seconds))
        self.system_monitor = system_monitor
        self.pending_critical_commands = {}
        self.device_wizard_sessions = {}
        self._current_trace_id = None

        self.started_at = time.time()
        self.processed_commands = 0
        self.rate_limited_commands = 0
        self.last_cleanup = retention_summary or {}
        self.intent_counts = {}
        self.stage_metrics = {
            "commands_timed": 0,
            "total_ms": 0.0,
            "slow_commands": 0,
            "p95_window_ms": [],
        }
        self.slow_command_threshold_ms = float(self.performance_config.get("slow_command_threshold_ms", 700))
        self.performance_enabled = bool(self.performance_config.get("enabled_metrics", True))

        self.precheck = CommandPrecheckPipeline(
            rate_limiter=self.rate_limiter,
            access_controller=self.access_controller,
            network_guard=self.network_guard,
            audit_logger=self.audit,
        )
        self.command_flow = CommandFlowPipeline()

    def perceive(self, data=None, output_callback=None):
        if data is None and self.interface is None:
            return None

        if data is None:
            data = self.interface.get_input()
        if not data:
            return None

        return self.prepare_perception_from_data(data=data, output_callback=output_callback)

    def prepare_perception_from_data(self, data, output_callback=None):
        parsed = self.command_flow.parse_input(data)
        if not parsed:
            return None

        content = parsed["content"]
        precheck = self.precheck.evaluate(
            content,
            skip_access_network=self.command_flow.is_exit_command(content),
        )

        emitter = output_callback or self._default_output
        for message in precheck.get("messages", []):
            if message and emitter is not None:
                emitter(message)
        for warning in precheck.get("warnings", []):
            if warning and emitter is not None:
                emitter(warning)

        if precheck.get("reason") == "rate_limit":
            self.rate_limited_commands += 1
        if precheck.get("status") == "deny":
            return None

        if self.command_flow.is_exit_command(content):
            self.stop()
            if emitter is not None:
                emitter("Encerrando JARVIS...")
            return None

        self.processed_commands += 1
        perception = dict(parsed)
        perception["user"] = precheck.get("user")

        logging.info("Percepcao [%s]: %s", perception["type"], content)
        if self.audit:
            self.audit.log(
                "agent.perception",
                mode=perception["type"],
                content=content,
                confidence=perception["confidence"],
            )
        return perception

    def analyze(self, perception):
        context = self.memory.recall(perception)
        analysis = self.llm.think(perception=perception, context=context)
        logging.info("Analise concluida")
        if self.audit:
            self.audit.log("agent.analysis", intent=analysis.get("intent", "unknown"))
            if analysis.get("intent") == "intrusion_check":
                self.audit.log(
                    "security.intrusion_detected",
                    severity="critical",
                    source=perception.get("type", "unknown"),
                    content=perception.get("content", ""),
                )
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

    def act(self, plan, perception=None):
        results = []
        if not plan:
            return results

        for step in plan["steps"]:
            try:
                if isinstance(step, dict) and step.get("action") == "confirm_critical_action":
                    results.append(self._confirm_critical_action(step=step, perception=perception))
                    continue

                if isinstance(step, dict) and step.get("action") == "device_wizard_start":
                    device = str(step.get("device", "")).strip().lower()
                    if not device:
                        results.append({"error": "Informe o nome do dispositivo para iniciar o assistente."})
                        continue
                    key = self._wizard_session_key(perception)
                    self.device_wizard_sessions[key] = {
                        "device": device,
                        "open_action": "",
                        "close_action": "",
                        "created_at": time.time(),
                    }
                    results.append(
                        {
                            "message": (
                                f"Assistente iniciado para '{device}'. Agora diga: "
                                "definir acao abrir <verbo> e depois definir acao fechar <verbo>."
                            )
                        }
                    )
                    continue

                if isinstance(step, dict) and step.get("action") == "device_wizard_set_open":
                    key = self._wizard_session_key(perception)
                    session = self.device_wizard_sessions.get(key)
                    if session is None:
                        results.append({"error": "Nenhum assistente ativo. Use: iniciar assistente de dispositivo <nome>."})
                        continue
                    open_action = str(step.get("open_action", "")).strip().lower()
                    if not open_action:
                        results.append({"error": "Informe uma acao de abrir valida."})
                        continue
                    session["open_action"] = open_action
                    results.append({"message": f"Acao de abrir definida: '{open_action}'."})
                    continue

                if isinstance(step, dict) and step.get("action") == "device_wizard_set_close":
                    key = self._wizard_session_key(perception)
                    session = self.device_wizard_sessions.get(key)
                    if session is None:
                        results.append({"error": "Nenhum assistente ativo. Use: iniciar assistente de dispositivo <nome>."})
                        continue
                    close_action = str(step.get("close_action", "")).strip().lower()
                    if not close_action:
                        results.append({"error": "Informe uma acao de fechar valida."})
                        continue
                    session["close_action"] = close_action
                    results.append({"message": f"Acao de fechar definida: '{close_action}'."})
                    continue

                if isinstance(step, dict) and step.get("action") == "device_wizard_finish":
                    key = self._wizard_session_key(perception)
                    session = self.device_wizard_sessions.get(key)
                    if session is None:
                        results.append({"error": "Nenhum assistente ativo para concluir."})
                        continue

                    device = str(session.get("device", "")).strip()
                    open_action = str(session.get("open_action", "")).strip()
                    close_action = str(session.get("close_action", "")).strip()
                    if not device or not open_action or not close_action:
                        results.append(
                            {
                                "error": (
                                    "Assistente incompleto. Defina abrir e fechar antes de concluir "
                                    "(definir acao abrir ... / definir acao fechar ...)."
                                )
                            }
                        )
                        continue

                    register_step = {
                        "tool": "home_control",
                        "action": "register_device",
                        "device": device,
                        "open_action": open_action,
                        "close_action": close_action,
                    }
                    tool_result = self._execute_tool_with_retry(register_step)
                    self.device_wizard_sessions.pop(key, None)
                    results.append(tool_result)
                    continue

                if isinstance(step, dict) and step.get("action") == "device_wizard_cancel":
                    key = self._wizard_session_key(perception)
                    self.device_wizard_sessions.pop(key, None)
                    results.append({"message": "Assistente de dispositivo cancelado."})
                    continue

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
                        semantic_limit = max(int(limit), int(getattr(self.long_memory, "semantic_top_k", limit)))
                        matches = self.long_memory.search(query, limit=semantic_limit)
                        if matches:
                            response_k = max(1, int(getattr(self.long_memory, "semantic_response_k", 3)))
                            selected = matches[:response_k]
                            summary = "; ".join(item.get("text", "") for item in selected)
                            lines = []
                            for item in selected:
                                ts = self._short_timestamp(item.get("timestamp", ""))
                                score = item.get("score")
                                if score is None:
                                    lines.append(f"[{ts}] {item.get('text', '')}")
                                else:
                                    lines.append(f"[{ts}] ({float(score):.2f}) {item.get('text', '')}")
                            evidence = " | ".join(lines)
                            results.append({"message": f"Encontrei na memoria. Resumo: {summary}\nTop resultados: {evidence}"})
                            if self.audit:
                                semantic_hits = sum(1 for item in matches if item.get("source") == "semantic")
                                self.audit.log(
                                    "memory.recall",
                                    query=query,
                                    matches=len(matches),
                                    semantic_hits=semantic_hits,
                                )
                        else:
                            results.append({"message": f"Nao encontrei nada salvo sobre '{query}'."})
                            if self.audit:
                                self.audit.log("memory.recall", query=query, matches=0)
                    continue

                if isinstance(step, dict) and step.get("action") == "status":
                    status = self.runtime_status()
                    results.append({"message": self.format_status_message(status), "status": status})
                    if self.audit:
                        self.audit.log("agent.status_requested", status=status)
                    continue

                if isinstance(step, dict) and step.get("action") == "memory_export":
                    if self.long_memory is None:
                        results.append({"error": "Memoria de longo prazo nao configurada."})
                    else:
                        output_path = step.get("path", "state/exports/memory-backup.enc")
                        password = step.get("password", "")
                        saved = self.long_memory.export_encrypted(output_path, password=password)
                        results.append({"message": f"Backup seguro criado em: {saved}", "path": saved})
                        if self.audit:
                            self.audit.log("memory.export", path=saved)
                    continue

                if isinstance(step, dict) and step.get("action") == "memory_import":
                    if self.long_memory is None:
                        results.append({"error": "Memoria de longo prazo nao configurada."})
                    else:
                        source_path = step.get("path", "state/exports/memory-backup.enc")
                        password = step.get("password", "")
                        report = self.long_memory.import_encrypted(source_path, password=password)
                        results.append(
                            {
                                "message": f"Backup importado com sucesso ({report['imported']} registros).",
                                "report": report,
                            }
                        )
                        if self.audit:
                            self.audit.log("memory.import", path=source_path, imported=report.get("imported", 0))
                    continue

                if self._step_requires_confirmation(step):
                    token = self._register_pending_critical(step=step, perception=perception)
                    if self.critical_confirmation_require_pin:
                        message = (
                            "Comando critico detectado e pausado por seguranca. "
                            f"Para confirmar, diga: confirmar comando {token} pin <seu_pin>"
                        )
                    else:
                        message = (
                            "Comando critico detectado e pausado por seguranca. "
                            f"Para confirmar, diga: confirmar comando {token}"
                        )
                    results.append({"message": message, "confirmation_token": token})
                    if self.audit:
                        self.audit.log(
                            "security.critical_confirmation_requested",
                            severity="warning",
                            token=token,
                            step=step,
                            user=(perception or {}).get("user"),
                        )
                    continue

                tool_result = self._execute_tool_with_retry(step)
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

    def process_command_data(self, data, output_callback=None, auto_remember=True):
        perception = self.prepare_perception_from_data(data=data, output_callback=output_callback)
        if not perception:
            return {"state": "skipped"}

        trace_id = uuid.uuid4().hex[:10]
        self._current_trace_id = trace_id
        self._audit_log("command.start", trace_id=trace_id, content=perception.get("content", ""))

        start_total = time.perf_counter()
        timings = {}

        stage_start = time.perf_counter()
        analysis = self.analyze(perception)
        timings["analyze_ms"] = round((time.perf_counter() - stage_start) * 1000, 3)
        self._audit_log("command.stage", trace_id=trace_id, stage="analyze", duration_ms=timings["analyze_ms"])

        stage_start = time.perf_counter()
        plan = self.plan(analysis)
        timings["plan_ms"] = round((time.perf_counter() - stage_start) * 1000, 3)
        self._audit_log("command.stage", trace_id=trace_id, stage="plan", duration_ms=timings["plan_ms"])

        stage_start = time.perf_counter()
        results = self.act(plan, perception=perception)
        timings["act_ms"] = round((time.perf_counter() - stage_start) * 1000, 3)
        self._audit_log("command.stage", trace_id=trace_id, stage="act", duration_ms=timings["act_ms"])

        timings["remember_ms"] = 0.0
        if auto_remember:
            stage_start = time.perf_counter()
            try:
                self.remember(perception, analysis, plan, results)
            except Exception as exc:
                logging.error("Falha ao gravar memoria: %s", exc)
            timings["remember_ms"] = round((time.perf_counter() - stage_start) * 1000, 3)
            self._audit_log("command.stage", trace_id=trace_id, stage="remember", duration_ms=timings["remember_ms"])

        timings["total_ms"] = round((time.perf_counter() - start_total) * 1000, 3)
        self._audit_log(
            "command.finish",
            trace_id=trace_id,
            duration_ms=timings["total_ms"],
            intent=(analysis or {}).get("intent", "unknown"),
        )
        self._record_performance_metrics(analysis=analysis, timings=timings)
        self._current_trace_id = None
        return {
            "state": "processed",
            "trace_id": trace_id,
            "perception": perception,
            "analysis": analysis,
            "plan": plan,
            "results": results,
            "timings_ms": timings,
        }

    def runtime_status(self):
        short_entries = len(getattr(self.memory, "data", []) or [])
        long_entries = len(getattr(self.long_memory, "data", []) or [])
        semantic = {}
        if self.long_memory is not None and hasattr(self.long_memory, "semantic_status"):
            semantic = self.long_memory.semantic_status()

        commands_timed = int(self.stage_metrics.get("commands_timed", 0))
        avg_total = 0.0
        if commands_timed > 0:
            avg_total = float(self.stage_metrics.get("total_ms", 0.0)) / commands_timed
        performance = {
            "enabled_metrics": self.performance_enabled,
            "commands_timed": commands_timed,
            "avg_total_ms": round(avg_total, 3),
            "p95_total_ms": self._percentile(self.stage_metrics.get("p95_window_ms", []), 95),
            "slow_commands": self.stage_metrics.get("slow_commands", 0),
            "slow_threshold_ms": self.slow_command_threshold_ms,
            "intent_counts": dict(self.intent_counts),
        }

        return {
            "mode": self.app_mode,
            "uptime": round(time.time() - self.started_at, 2),
            "processed_commands": self.processed_commands,
            "rate_limited_commands": self.rate_limited_commands,
            "pending_critical_confirmations": len(self.pending_critical_commands),
            "short_term_entries": short_entries,
            "long_term_entries": long_entries,
            "last_cleanup": self.last_cleanup,
            "semantic_memory": semantic,
            "access_control_enabled": bool(self.access_controller is not None and getattr(self.access_controller, "enabled", False)),
            "network_guard_enabled": bool(self.network_guard is not None and getattr(self.network_guard, "enabled", False)),
            "performance": performance,
            "system_resources": self._system_resources_status(),
        }

    @staticmethod
    def format_status_message(status: dict):
        cleanup = status.get("last_cleanup") or {}
        cleanup_info = (
            f"deleted={cleanup.get('deleted', 0)}"
            if isinstance(cleanup, dict) and cleanup
            else "indisponivel"
        )
        return (
            f"Status | mode={status.get('mode')} | uptime={status.get('uptime')}s | "
            f"commands={status.get('processed_commands')} | "
            f"rate_limited={status.get('rate_limited_commands')} | "
            f"pending_confirmations={status.get('pending_critical_confirmations', 0)} | "
            f"memory(short={status.get('short_term_entries')}, long={status.get('long_term_entries')}) | "
            f"cleanup={cleanup_info} | semantic={status.get('semantic_memory', {}).get('ready', False)} | "
            f"access_control={status.get('access_control_enabled', False)} | "
            f"network_guard={status.get('network_guard_enabled', False)} | "
            f"p95_ms={status.get('performance', {}).get('p95_total_ms', 0.0)} | "
            f"cpu={status.get('system_resources', {}).get('cpu_percent', 'n/a')}% | "
            f"ram={status.get('system_resources', {}).get('memory_percent', 'n/a')}%"
        )

    @staticmethod
    def _short_timestamp(value):
        value = str(value or "").strip()
        if not value:
            return "sem-data"
        return value[:19]

    def run(self):
        self.interface.output(f"JARVIS online ({self.app_mode}). Sempre escutando...")

        while self.running:
            data = self.interface.get_input()
            if not data:
                time.sleep(0.05)
                continue

            payload = self.process_command_data(data=data, output_callback=self.interface.output, auto_remember=True)
            if payload.get("state") != "processed":
                time.sleep(0.05)
                continue

            for result in payload.get("results", []):
                if isinstance(result, dict):
                    if "message" in result:
                        self.interface.output(result["message"])
                    elif "error" in result:
                        self.interface.output(f"Erro: {result['error']}")

    def stop(self):
        self.running = False
        logging.info("Agente desligado")
        if self.audit:
            self.audit.log("agent.stop")

    def _record_performance_metrics(self, analysis: dict, timings: dict):
        intent = str((analysis or {}).get("intent", "unknown"))
        self.intent_counts[intent] = self.intent_counts.get(intent, 0) + 1

        total_ms = float(timings.get("total_ms", 0.0))
        self.stage_metrics["commands_timed"] += 1
        self.stage_metrics["total_ms"] += total_ms
        window = self.stage_metrics["p95_window_ms"]
        window.append(total_ms)
        if len(window) > 200:
            del window[0]

        if total_ms >= self.slow_command_threshold_ms:
            self.stage_metrics["slow_commands"] += 1
            if self.performance_enabled and self.audit:
                self.audit.log(
                    "performance.slow_command",
                    severity="warning",
                    intent=intent,
                    total_ms=total_ms,
                    timings_ms=timings,
                )

    def _step_requires_confirmation(self, step):
        if not self.critical_confirmation_enabled:
            return False
        if not isinstance(step, dict):
            return False
        if step.get("_confirmed", False):
            return False
        if step.get("tool") != "network_enforce":
            return False

        critical_actions = {
            "block_internet_global",
            "unblock_internet_global",
            "block_machine_internet",
            "unblock_machine_internet",
            "block_machine_isolate",
            "unblock_machine",
        }
        return str(step.get("action", "")).strip().lower() in critical_actions

    def _register_pending_critical(self, step, perception):
        token = uuid.uuid4().hex[:8]
        self.pending_critical_commands[token] = {
            "step": dict(step),
            "created_at": time.time(),
            "user": (perception or {}).get("user"),
        }
        return token

    def _confirm_critical_action(self, step, perception):
        token = str(step.get("token", "") or step.get("code", "")).strip().lower()
        pin = str(step.get("pin", "")).strip()
        if not token:
            if self.critical_confirmation_require_pin:
                return {"error": "Informe token e PIN: confirmar comando <token> pin <seu_pin>."}
            return {"error": "Informe o token de confirmacao: confirmar comando <token>."}

        pending = self.pending_critical_commands.get(token)
        if pending is None:
            return {"error": f"Token '{token}' invalido ou expirado."}

        age_seconds = time.time() - float(pending.get("created_at", 0.0))
        if age_seconds > float(self.critical_confirmation_ttl_seconds):
            self.pending_critical_commands.pop(token, None)
            return {"error": f"Token '{token}' expirou. Repita o comando critico para gerar um novo token."}

        requester = (perception or {}).get("user")
        owner_name = getattr(self.access_controller, "owner_name", "") if self.access_controller is not None else ""
        pending_user = pending.get("user")
        if pending_user and requester and requester != pending_user and requester != owner_name:
            return {"error": "Somente o mesmo usuario (ou dono) pode confirmar este comando critico."}

        if self.critical_confirmation_require_pin:
            expected_pin = os.getenv(self.critical_confirmation_pin_env, "").strip()
            if not expected_pin:
                return {
                    "error": (
                        f"PIN administrativo nao configurado. Defina a variavel de ambiente {self.critical_confirmation_pin_env}."
                    )
                }
            if not pin:
                return {"error": "PIN obrigatorio. Use: confirmar comando <token> pin <seu_pin>."}
            if pin != expected_pin:
                return {"error": "PIN invalido para confirmacao de comando critico."}

        original_step = dict(pending["step"])
        original_step["_confirmed"] = True
        self.pending_critical_commands.pop(token, None)

        tool_result = self._execute_tool_with_retry(original_step)
        if isinstance(tool_result, dict):
            message = str(tool_result.get("message", "")).strip()
            if message:
                tool_result["message"] = f"[CONFIRMADO] {message}"
        if self.audit:
            self.audit.log(
                "security.critical_confirmation_approved",
                severity="warning",
                token=token,
                step=original_step,
                user=requester,
            )
        return tool_result

    def _execute_tool_with_retry(self, step):
        last_error = None
        for attempt in range(self.tool_retry_attempts + 1):
            try:
                return self.tools.execute(step)
            except Exception as exc:
                last_error = exc
                if self.audit:
                    self.audit.log(
                        "tool.retry",
                        severity="warning",
                        tool=str((step or {}).get("tool", "unknown")) if isinstance(step, dict) else str(step),
                        attempt=attempt + 1,
                        max_attempts=self.tool_retry_attempts + 1,
                        error=str(exc),
                    )
                if attempt < self.tool_retry_attempts and self.tool_retry_backoff_seconds > 0:
                    time.sleep(self.tool_retry_backoff_seconds)

        raise last_error

    def _default_output(self, message):
        if self.interface is not None:
            self.interface.output(message)

    @staticmethod
    def _percentile(values, percentile):
        if not values:
            return 0.0
        ordered = sorted(float(v) for v in values)
        index = int(round((percentile / 100.0) * (len(ordered) - 1)))
        index = max(0, min(index, len(ordered) - 1))
        return round(ordered[index], 3)

    def _audit_log(self, event, severity="info", **data):
        if self.audit is None:
            return
        trace_id = str(data.get("trace_id", "")).strip() or str(self._current_trace_id or "").strip()
        if trace_id:
            data["trace_id"] = trace_id
        self.audit.log(event, severity=severity, **data)

    @staticmethod
    def _wizard_session_key(perception):
        user = str((perception or {}).get("user", "")).strip().lower()
        return user or "_default"

    def _system_resources_status(self):
        if self.system_monitor is None:
            return {
                "enabled": False,
                "available": False,
            }

        try:
            monitor_status = self.system_monitor.status()
            latest = monitor_status.get("latest", {}) if isinstance(monitor_status, dict) else {}
            return {
                "enabled": bool(monitor_status.get("enabled", True)),
                "available": True,
                "running": bool(monitor_status.get("running", False)),
                "cpu_percent": latest.get("cpu_percent"),
                "memory_percent": latest.get("memory_percent"),
                "memory_used_mb": latest.get("memory_used_mb"),
                "memory_total_mb": latest.get("memory_total_mb"),
            }
        except Exception:
            return {
                "enabled": True,
                "available": False,
            }
