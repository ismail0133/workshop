# Limites connues — pilier IA

Version 1.0 — 21 octobre 2026. Ce qui n'est pas prouvé est dit ici.

## 3. Intelligence artificielle

- **Détecteur ML** : aucune performance n'est démontrée sur l'environnement réel. Le jeu synthétique ne sert qu'à tester le pipeline. Cibles à vérifier sur le PC Hôte : rappel ≥ 0,8, précision ≥ 0,8, détection ≤ 15 s, ≤ 1 fausse alerte par 10 min.
- Un modèle entraîné ailleurs n'est pas valable sur le PC Hôte (quota CPU, latences, version de scikit-learn) : réentraîner sur la cible.
- Sans paiement ni trafic dans la fenêtre, le détecteur déclare la fenêtre invalide (`NO_TRAFFIC`, `NO_PAYMENT_ATTEMPT`) : le client de référence (1 requête/s, un paiement régulier) doit rester actif pendant les essais.
- **Assistant RAG** : tests unitaires réalisés avec de faux embeddings et un faux modèle, sans Ollama. La qualité en français de `nomic-embed-text` et de `qwen2.5:1.5b`, le seuil d'abstention (0,45 par défaut) et la résistance du modèle réel à l'injection de prompt restent **à mesurer** avec la recette de `rag_eval/`.
- Le rôle ADMIN n'a pas accès à l'assistant (contrat OpenAPI : OPERATOR seulement) ; à arbitrer par l'équipe.
- La désactivation d'un compte reste effective au plus tard à l'expiration du JWT (15 min) : le service RAG n'accède pas à la base.


## Livraison

- Les images Docker des services IA n'ont pas été construites ni démarrées dans l'environnement de rédaction (pas de démon Docker) : `NOT TESTED` jusqu'à la recette sur le PC Hôte.
- **Détecteur WAF (par User-Agent)** : une seule session réelle (31 min, un navigateur, un outil d'attaque). Précision non probante (0 fenêtre normale « fournie » dans le test) ; 7 fenêtres normales sur 11 jugées atypiques ; une règle sur le seul débit fait aussi bien ; contournable en changeant ou en faisant tourner le User-Agent. Détail : `docs/ml/ML_REPORT.md` §7.
- Le détecteur WAF n'écrit dans `blocklist.txt` qu'avec `--apply` ; l'écriture n'est pas verrouillée contre l'orchestrateur de remédiation (fenêtre de course de quelques millisecondes).
- Un client de supervision qui interroge une seule URL à cadence régulière ressemble à l'attaque : le déclarer avec `--never-block`.
