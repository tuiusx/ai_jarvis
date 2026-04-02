import json
import os
import re
import unicodedata

try:
    import yaml
except Exception:  # pragma: no cover - fallback para ambientes sem PyYAML
    yaml = None

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - fallback para ambientes sem SDK OpenAI
    OpenAI = None


class LocalLLM:
    def __init__(self):
        config_path = "config/settings.yaml"
        self.config = {}
        if os.path.exists(config_path) and yaml is not None:
            with open(config_path, "r", encoding="utf-8") as file:
                self.config = yaml.safe_load(file) or {}

        api_key = os.getenv("OPENAI_API_KEY") or self.config.get("openai", {}).get("api_key", "")
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
        content = self._normalize(content_raw)

        if any(k in content for k in ["invas", "intrus", "estranh", "desconhec", "parede", "escura"]):
            return {
                "intent": "intrusion_check",
                "response": "Detectei um possivel risco. Vou ligar a vigilancia e monitorar rostos desconhecidos.",
                "needs_action": True,
                "action": "surveillance_start",
            }

        if any(k in content for k in ["iniciar vigilancia", "ligar vigilancia", "comecar vigilancia", "vigiar ambiente"]):
            return {
                "intent": "surveillance_start",
                "response": "Vigilancia ativada. Monitorando ambiente.",
                "needs_action": True,
                "action": "surveillance_start",
            }

        if any(k in content for k in ["parar vigilancia", "desligar vigilancia", "pausar vigilancia"]):
            return {
                "intent": "surveillance_stop",
                "response": "Vigilancia pausada.",
                "needs_action": True,
                "action": "surveillance_stop",
            }

        if any(
            k in content
            for k in [
                "escanear rede",
                "scanear rede",
                "varrer rede",
                "dispositivos na rede",
                "quem esta na rede",
                "quem esta conectado",
                "rede da casa",
                "wifi da casa",
            ]
        ):
            return {
                "intent": "network_scan",
                "response": "Vou identificar os dispositivos visiveis na rede da casa.",
                "needs_action": True,
                "action": "network_scan",
            }

        remember_match = re.match(r"^\s*(?:lembre|guarde|memorize)(?:\s+que)?\s+(.+)$", content)
        if remember_match:
            return {
                "intent": "remember",
                "memory": remember_match.group(1).strip(),
                "response": "Posso guardar isso na memoria.",
                "needs_action": True,
            }

        recall_match = re.match(r"^\s*o que voce sabe sobre\s+(.+?)[\?]?\s*$", content)
        if recall_match:
            return {
                "intent": "recall",
                "query": recall_match.group(1).strip(),
                "limit": 2,
                "response": "Vou consultar minha memoria sobre isso.",
                "needs_action": True,
            }

        if self._looks_like_question(content):
            answer = self.generate(content_raw, context=context)
            if answer.lower().startswith("erro no llm:"):
                answer = "Estou sem acesso ao provedor de respostas agora, mas sigo pronto para comandos da casa, vigilancia e rede local."
            return {
                "intent": "question_answer",
                "response": answer,
                "needs_action": False,
            }

        home_command = self._match_home_command(content)
        if home_command:
            return home_command

        if any(k in content for k in ["ola", "oi", "bom dia", "boa tarde", "boa noite"]):
            return {
                "intent": "greeting",
                "response": "Ola! Estou pronto para proteger sua casa e controlar seus dispositivos.",
                "needs_action": False,
            }

        if any(k in content for k in ["status", "como esta", "tudo bem"]):
            return {
                "intent": "status",
                "response": "Estou online. Voce pode controlar luz, tomada, fechadura, iniciar vigilancia, escanear a rede da casa ou fazer perguntas.",
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

    def _match_home_command(self, content):
        content = self._normalize(content)
        device_aliases = {
            "luz": ["luz", "lampada", "lâmpada", "iluminacao", "iluminação"],
            "tomada": ["tomada", "plug", "energia da tomada"],
            "fechadura": ["fechadura", "porta", "porta da casa", "tranca"],
        }
        action_aliases = {
            "on": ["ligar", "acender", "ativar"],
            "off": ["desligar", "apagar", "desativar"],
            "lock": ["trancar", "fechar", "bloquear"],
            "unlock": ["destrancar", "abrir", "liberar"],
        }
        responses = {
            ("luz", "on"): "Ligando a luz da casa.",
            ("luz", "off"): "Desligando a luz da casa.",
            ("tomada", "on"): "Ligando a tomada da casa.",
            ("tomada", "off"): "Desligando a tomada da casa.",
            ("fechadura", "lock"): "Trancando a fechadura da casa.",
            ("fechadura", "unlock"): "Destrancando a fechadura da casa.",
        }

        for device, aliases in device_aliases.items():
            if not any(alias in content for alias in aliases):
                continue

            candidate_actions = ("unlock", "lock") if device == "fechadura" else ("off", "on")
            for action in candidate_actions:
                if any(alias in content for alias in action_aliases[action]):
                    return {
                        "intent": "home_control",
                        "device": device,
                        "action": action,
                        "response": responses[(device, action)],
                        "needs_action": True,
                    }

        return None

    @staticmethod
    def _looks_like_question(content: str):
        if not content:
            return False
        if "?" in content:
            return True
        starters = ("o que", "qual", "quais", "como", "quando", "onde", "por que", "porque", "quem", "quanto", "me explica", "explique")
        return content.strip().startswith(starters)

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", str(text).lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")
