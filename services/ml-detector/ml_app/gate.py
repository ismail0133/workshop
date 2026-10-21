"""Règle de déclenchement : 2 scores consécutifs sous le seuil, anti-flap et déduplication."""

from __future__ import annotations


class AlertGate:
    """Machine à états pure (testable) partagée par l'évaluation et le détecteur temps réel.

    - déclenche après `consecutive` fenêtres anormales valides consécutives ;
    - se désarme ensuite : une seule alerte par épisode (déduplication d'incident) ;
    - se réarme après `rearm_normal` fenêtres normales consécutives ET `cooldown_s` écoulées
      (cohérent avec le cooldown de 60 s de REMEDIATION_DESIGN) ;
    - une fenêtre invalide (DATA_UNAVAILABLE) interrompt la série sans compter comme normale.
    """

    def __init__(self, consecutive: int = 2, rearm_normal: int = 3, cooldown_s: float = 60.0):
        self.consecutive, self.rearm_normal, self.cooldown_s = consecutive, rearm_normal, cooldown_s
        self.run = self.normal_run = 0
        self.armed = True
        self.last_fire = float("-inf")

    def reset_run(self) -> None:
        self.run = 0

    def update(self, anomalous: bool, now: float) -> bool:
        if anomalous:
            self.run += 1
            self.normal_run = 0
            if self.run >= self.consecutive and self.armed:
                self.armed, self.last_fire = False, now
                return True
            return False
        self.run = 0
        self.normal_run += 1
        if not self.armed and self.normal_run >= self.rearm_normal:
            if now - self.last_fire >= self.cooldown_s:
                self.armed = True
        return False
