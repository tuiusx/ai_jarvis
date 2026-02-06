class Planner:
    def decide(self, user_input: str) -> dict:
        text = user_input.lower()

        if "vigiar" in text or "monitorar" in text:
            return {
                "type": "tool",
                "name": "detect_people",
                "args": {
                    "duration": 20
                }
            }

        return {
            "type": "respond"
        }
