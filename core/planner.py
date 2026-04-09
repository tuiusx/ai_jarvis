import re
import unicodedata


class Planner:
    def create_plan(self, analysis):
        if not analysis:
            return None

        intent = analysis.get("intent", "unknown")
        default_response = {
            "surveillance_start": "Vigilancia iniciada.",
            "intrusion_check": "Vigilancia iniciada.",
            "surveillance_stop": "Vigilancia interrompida.",
            "home_control": "Comando de automacao executado.",
            "network_scan": "Escaneando.",
            "question_answer": "Resposta direta.",
        }.get(intent, "Entendi.")
        response = analysis.get("response") or default_response
        analysis = {**analysis, "response": response}

        if intent in ["surveillance_start", "intrusion_check"]:
            return {
                "steps": [
                    {"tool": "surveillance", "action": "start", "duration": analysis.get("duration", 20)},
                    {"action": "respond", "message": analysis.get("response", "VigilÃ¢ncia iniciada.")},
                ]
            }

        if intent == "surveillance_stop":
            return {
                "steps": [
                    {"tool": "surveillance", "action": "stop"},
                    {"action": "respond", "message": analysis.get("response", "VigilÃ¢ncia interrompida.")},
                ]
            }

        if intent == "home_control":
            return {
                "steps": [
                    {
                        "tool": "home_control",
                        "device": analysis.get("device", "luz"),
                        "action": analysis.get("action", "on"),
                    },
                    {"action": "respond", "message": analysis.get("response", "Comando de automaÃ§Ã£o executado.")},
                ]
            }

        if intent == "record":
            return {"steps": [{"tool": "start_recording", "duration": analysis.get("duration", 10)}]}

        if intent == "network_scan":
            return {
                "steps": [
                    {"tool": "network_scan", "limit": analysis.get("limit", 50)},
                    {"action": "respond", "message": analysis.get("response", "Escaneando.")},
                ]
            }

        if intent == "question_answer":
            return {"steps": [{"action": "respond", "message": analysis.get("response", "Resposta direta.")}]}

        if intent == "remember":
            return {"steps": [{"action": "remember", "text": analysis.get("memory", "")}]}

        if intent == "recall":
            return {
                "steps": [
                    {
                        "action": "recall",
                        "query": analysis.get("query", ""),
                        "limit": analysis.get("limit", 2),
                    }
                ]
            }

        return {"steps": [{"action": "respond", "message": analysis.get("response", "Entendi.")}]}

    def create_plan(self, analysis):
        if not analysis:
            return None

        intent = analysis.get("intent", "unknown")
        response = analysis.get("response") or {
            "surveillance_start": "Vigilancia iniciada.",
            "intrusion_check": "Vigilancia iniciada.",
            "surveillance_stop": "Vigilancia interrompida.",
            "home_control": "Comando de automacao executado.",
            "network_scan": "Escaneando.",
            "question_answer": "Resposta direta.",
        }.get(intent, "Entendi.")

        if intent in {"surveillance_start", "intrusion_check"}:
            return {
                "steps": [
                    {"tool": "surveillance", "action": "start", "duration": analysis.get("duration", 20)},
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "surveillance_stop":
            return {"steps": [{"tool": "surveillance", "action": "stop"}, {"action": "respond", "message": response}]}

        if intent == "home_control":
            return {
                "steps": [
                    {
                        "tool": "home_control",
                        "device": analysis.get("device", "luz"),
                        "action": analysis.get("action", "on"),
                    },
                    {"action": "respond", "message": response},
                ]
            }

        if intent == "record":
            return {"steps": [{"tool": "start_recording", "duration": analysis.get("duration", 10)}]}

        if intent == "network_scan":
            return {"steps": [{"tool": "network_scan", "limit": analysis.get("limit", 50)}, {"action": "respond", "message": response}]}

        if intent == "question_answer":
            return {"steps": [{"action": "respond", "message": response}]}

        if intent == "remember":
            return {"steps": [{"action": "remember", "text": analysis.get("memory", "")}]}

        if intent == "recall":
            return {"steps": [{"action": "recall", "query": analysis.get("query", ""), "limit": analysis.get("limit", 2)}]}

        return {"steps": [{"action": "respond", "message": response}]}

    def decide(self, text: str):
        original = text.strip()
        if not original:
            return {"type": "ignore"}

        normalized = self._normalize(original)

        if "vigiar ambiente" in normalized or normalized in {"iniciar vigilancia", "iniciar vigia"}:
            return {"type": "start_surveillance"}

        if "parar vigilancia" in normalized or "interromper vigilancia" in normalized:
            return {"type": "stop_surveillance"}

        parts = original.split(maxsplit=3)
        if len(parts) == 4 and self._normalize(" ".join(parts[:3])) == "esse rosto e":
            return {"type": "label_face", "name": parts[3].strip()}

        label_match_clean = re.match(r"^\s*esse rosto [eEéÉ]\s+(.+)$", original, flags=re.IGNORECASE)
        if label_match_clean:
            return {"type": "label_face", "name": label_match_clean.group(1).strip()}

        label_match = re.match(r"^\s*esse rosto [eEÃ©Ã‰]\s+(.+)$", original, flags=re.IGNORECASE)
        if label_match:
            return {"type": "label_face", "name": label_match.group(1).strip()}

        remember_match = re.match(r"^\s*(?:lembre|guarde|memorize)(?:\s+que)?\s+(.+)$", original, flags=re.IGNORECASE)
        if remember_match:
            return {"type": "remember", "memory": remember_match.group(1).strip()}

        for pattern in (
            r"^\s*o que voce sabe sobre\s+(.+)$",
            r"^\s*o que voce lembra sobre\s+(.+)$",
            r"^\s*procure na memoria\s+(.+)$",
        ):
            recall_match = re.match(pattern, normalized, flags=re.IGNORECASE)
            if recall_match:
                return {"type": "recall", "query": recall_match.group(1).strip()}

        if "rostos conhecidos" in normalized or "quem voce conhece" in normalized or "quais rostos conhecidos" in normalized:
            return {"type": "list_known_faces"}

        return {"type": "respond"}

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", text.lower())
        return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

    @staticmethod
    def _sanitize_text(text: str):
        mapping = {
            "Ã¢": "a",
            "Ã¡": "a",
            "Ã£": "a",
            "Ã§": "c",
            "Ã©": "e",
            "Ãª": "e",
            "Ã­": "i",
            "Ã³": "o",
            "Ã´": "o",
            "Ãº": "u",
            "Ã‰": "E",
        }
        value = str(text)
        for bad, good in mapping.items():
            value = value.replace(bad, good)
        return value
