class Tool:
    name = ""
    description = ""

    def run(self, **kwargs):
        raise NotImplementedError("Ferramenta não implementada")
