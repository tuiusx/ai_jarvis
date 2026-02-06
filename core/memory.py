from collections import deque

class ShortTermMemory:
    def __init__(self, max_messages: int = 10):
        self.history = deque(maxlen=max_messages)

    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def get_context(self) -> str:
        return "\n".join(
            [f"{m['role']}: {m['content']}" for m in self.history]
        )


class LongTermMemory:
    def __init__(self):
        self.storage = []

    def add(self, text: str):
        self.storage.append(text)

    def search(self, query: str, k: int = 3):
        return self.storage[-k:]
