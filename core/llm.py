class LocalLLM:
    def generate(
        self,
        prompt: str,
        context: str = "",
        memories=None,
    ) -> str:
        normalized = self._normalize(prompt)
        memories = memories or []

        if any(
            greeting in normalized
            for greeting in ("oi", "ola", "bom dia", "boa tarde", "boa noite")
        ):
            return (
                "Oi. Posso iniciar a vigilancia, cadastrar rostos "
                "e guardar memorias simples."
            )

        if "quem voce e" in normalized or "quem e voce" in normalized:
            return (
                "Sou o assistente local deste projeto. Hoje opero com "
                "comandos, memoria simples e vigilancia."
            )

        if (
            "o que voce faz" in normalized
            or "como voce funciona" in normalized
            or "ajuda" in normalized
        ):
            return (
                "Consigo vigiar o ambiente, gravar o stream atual sem "
                "reabrir a camera, cadastrar rostos e consultar memorias simples."
            )

        if memories:
            return (
                "Encontrei isto na memoria relacionado ao que voce disse: "
                + "; ".join(memories[:3])
            )

        recent_lines = [line for line in context.splitlines() if line.strip()]
        if recent_lines:
            recent_context = " | ".join(recent_lines[-2:])
            return (
                "Ainda estou em modo local sem um modelo generativo conectado. "
                "Posso agir sobre vigilancia, rostos e memoria simples. "
                f"Contexto recente: {recent_context}"
            )

        return (
            "Ainda estou em modo local sem um modelo generativo conectado. "
            "Posso ajudar com vigilancia, cadastro de rostos e memoria simples."
        )

    @staticmethod
    def _normalize(text: str):
        import unicodedata

        normalized = unicodedata.normalize("NFD", text.lower())
        return "".join(
            char for char in normalized
            if unicodedata.category(char) != "Mn"
        )
