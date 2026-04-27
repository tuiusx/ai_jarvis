import json
import os

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback para ambientes sem SDK OpenAI
    OpenAI = None

from core.intent_router import IntentRouter
from core.settings import load_settings


class LocalLLM:
    def __init__(self, settings=None, router=None):
        self.config = settings or load_settings()
        custom_commands_path = self.config.get("home_automation", {}).get("custom_devices_path", "state/home_custom_devices.json")
        plugins_cfg = self.config.get("plugins", {}) or {}
        self.router = router or IntentRouter(
            custom_commands_path=str(custom_commands_path),
            plugin_directory=str(plugins_cfg.get("directory", "state/plugins")),
            plugins_enabled=bool(plugins_cfg.get("enabled", True)),
        )
        app_mode = self.config.get("app", {}).get("mode", "dev")
        enforce_env_secrets = bool(self.config.get("security", {}).get("enforce_env_secrets", False))
        api_key = os.getenv("OPENAI_API_KEY") or self.config.get("openai", {}).get("api_key", "")
        if app_mode == "prod" and enforce_env_secrets and "OPENAI_API_KEY" not in os.environ:
            api_key = ""
        self.model = self.config.get("openai", {}).get("model", "gpt-3.5-turbo")
        self.client = OpenAI(api_key=api_key) if api_key and OpenAI is not None else None

    def generate(self, prompt: str, context: str = "") -> str:
        if self.client is None:
            return "Estou pronto para responder, mas no momento estou sem conexao com o provedor de respostas."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            return f"Erro no LLM: {exc}"

    def think(self, perception, context):
        content_raw = str(perception.get("content", "")).strip()
        content = self.router.normalize(content_raw)

        routed = self.router.route(content_raw)
        if routed is not None:
            return routed

        if self.router.looks_like_question(content):
            answer = self.generate(content_raw, context=context)
            if answer.lower().startswith("erro no llm:"):
                answer = "Estou sem acesso ao provedor de respostas agora, mas sigo pronto para comandos da casa, vigilancia e rede local."
            return {
                "intent": "question_answer",
                "response": answer,
                "needs_action": False,
            }

        if self.client is not None:
            try:
                prompt = f"""
                Voce e JARVIS, um assistente de IA inteligente e seguro. Responda em portugues.
                Contexto: {context}
                Comando: {content_raw}
                Gere um JSON com intent, response, needs_action e action (opcional).
                """
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Voce e um assistente que responde apenas com JSON valido."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=200,
                    temperature=0.3,
                )
                result = json.loads(response.choices[0].message.content.strip())
                result.setdefault("intent", "unknown")
                result.setdefault("response", "Desculpe, nao entendi.")
                result.setdefault("needs_action", False)
                return result
            except Exception:
                pass

        return {
            "intent": "unknown",
            "response": "Desculpe, nao entendi. Tente algo como 'ligar a luz da casa', 'desligar a tomada' ou 'trancar a fechadura'.",
            "needs_action": False,
        }
