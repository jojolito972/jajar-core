# Agent Cesare - Intégré à l'écosystème JARVIS
class CesareAgent:
    def __init__(self):
        self.nom = "Cesare"
        self.role = "Expert Opérationnel & Gestion d'Atelier"
    def repondre(self, message):
        return f"[Cesare] J'ai bien reçu : {message}. Prêt pour l'action."
