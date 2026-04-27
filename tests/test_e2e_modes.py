import unittest

from core.agent import Agent


class _E2ELLM:
    def think(self, perception, context):
        content = str(perception.get("content", "")).lower()
        if "status" in content:
            return {"intent": "status", "response": "status", "needs_action": True}
        return {"intent": "home_control", "device": "luz", "action": "on", "response": "ligando", "needs_action": True}


class _E2EPlanner:
    def create_plan(self, analysis):
        if analysis.get("intent") == "status":
            return {"steps": [{"action": "status"}]}
        return {"steps": [{"tool": "home_control", "device": "luz", "action": "on"}]}


class _E2EMemory:
    def recall(self, perception):
        return ""

    def store(self, experience):
        return None


class _E2ETools:
    def execute(self, step):
        if step.get("tool") == "home_control":
            return {"message": "ok home"}
        if step.get("action") == "status":
            return {"message": "ok status"}
        return {"message": "ok"}


class E2EModesTests(unittest.TestCase):
    def test_text_and_voice_modes_process_same_flow(self):
        agent = Agent(
            llm=_E2ELLM(),
            memory=_E2EMemory(),
            planner=_E2EPlanner(),
            tools=_E2ETools(),
            interface=None,
        )

        text_payload = agent.process_command_data(
            data={"mode": "text", "content": "ligar luz", "confidence": 1.0},
            auto_remember=True,
        )
        voice_payload = agent.process_command_data(
            data={"mode": "voice", "content": "ligar luz", "confidence": 0.9},
            auto_remember=True,
        )

        self.assertEqual(text_payload["state"], "processed")
        self.assertEqual(voice_payload["state"], "processed")
        self.assertEqual(text_payload["analysis"]["intent"], "home_control")
        self.assertEqual(voice_payload["analysis"]["intent"], "home_control")


if __name__ == "__main__":
    unittest.main()
