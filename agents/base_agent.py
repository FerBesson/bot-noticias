class BaseAgent:
    def __init__(self, name: str):
        self.name = name

    def setup_schedule(self, scheduler):
        """Registra el agente en la instancia de schedule."""
        pass

    def run(self):
        """Método de ejecución principal o manual."""
        pass
