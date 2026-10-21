"""Détecteur par User-Agent sur les journaux du WAF (`access.jsonl`).

Chaîne : journal WAF -> fenêtres de 10 s par User-Agent -> 7 caractéristiques -> Isolation Forest
-> règle d'alerte (2 fenêtres consécutives) -> ligne `ua:Token` dans `blocklist.txt`.

Le modèle ne voit jamais la chaîne du User-Agent : seulement le comportement agrégé (débit, erreurs,
variété des URI, durée, part de POST). Le User-Agent sert d'identité à bloquer et, dans le jeu d'essai
de laboratoire, de marqueur de vérité terrain (jamais d'entrée du modèle).
"""

WAF_SCHEMA_VERSION = "waf-fs-1"
WINDOW_S = 10
STEP_S = 5
