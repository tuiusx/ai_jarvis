class ShortTermMemory:
    def __init__(self):
        self.data = []

    def add(self, who, text):
        self.data.append(f"{who}: {text}")
        self.data = self.data[-10:]

    def get_context(self):
        return "\n".join(self.data)


class LongTermMemory:
    def add(self, text):
        pass

    def search(self, query):
        return []
