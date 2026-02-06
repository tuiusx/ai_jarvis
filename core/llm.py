class BaseLLM:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


class LocalLLM(BaseLLM):
    def generate(self, prompt: str) -> str:
        return f"[LLM LOCAL MOCK]\n{prompt[:300]}"
