import re
import unicodedata


class Planner:
    def decide(self, text: str):
        original = text.strip()
        if not original:
            return {"type": "ignore"}

        normalized = self._normalize(original)

        if "vigiar ambiente" in normalized or normalized in {
            "iniciar vigilancia",
            "iniciar vigia",
        }:
            return {"type": "start_surveillance"}

        if "parar vigilancia" in normalized or "interromper vigilancia" in normalized:
            return {"type": "stop_surveillance"}

        label_match = re.match(
            r"^\s*esse rosto [eEéÉ]\s+(.+)$",
            original,
            flags=re.IGNORECASE,
        )
        if label_match:
            return {
                "type": "label_face",
                "name": label_match.group(1).strip(),
            }

        remember_match = re.match(
            r"^\s*(?:lembre|guarde|memorize)(?:\s+que)?\s+(.+)$",
            original,
            flags=re.IGNORECASE,
        )
        if remember_match:
            return {
                "type": "remember",
                "memory": remember_match.group(1).strip(),
            }

        for pattern in (
            r"^\s*o que voce sabe sobre\s+(.+)$",
            r"^\s*o que voce lembra sobre\s+(.+)$",
            r"^\s*procure na memoria\s+(.+)$",
        ):
            recall_match = re.match(pattern, normalized, flags=re.IGNORECASE)
            if recall_match:
                return {
                    "type": "recall",
                    "query": recall_match.group(1).strip(),
                }

        if (
            "rostos conhecidos" in normalized
            or "quem voce conhece" in normalized
            or "quais rostos conhecidos" in normalized
        ):
            return {"type": "list_known_faces"}

        return {"type": "respond"}

    @staticmethod
    def _normalize(text: str):
        normalized = unicodedata.normalize("NFD", text.lower())
        return "".join(
            char for char in normalized
            if unicodedata.category(char) != "Mn"
        )
