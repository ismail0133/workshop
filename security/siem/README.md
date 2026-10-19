# SOC intégré — contrat de corrélation

Implémentation future : `services/incident-service/soc/`. Loki est le stockage ; le module Python est la fonction SOC. Règle SOC-SC01-v1 : fenêtre 15 s, requêtes WAF sur routes Payment ≥20, IP unique dominante ≥70 %, ≥10 request_id joints avec logs applicatifs, dégradation mesurée. Exclusions : hôte, passerelle, validateur, PC IA et toute IP non autorisée. L’IP vient du socket TCP observé au WAF, jamais d’un en-tête client.

Sortie SOC_EVIDENCE : event_id UUID, incident_id, occurred_at UTC, rule_id, window_start/end, source_ip, request_count, source_share, matched_request_ids (max 50), evidence_refs (max 20), decision CONFIRMED/INSUFFICIENT/AMBIGUOUS, reason. Conserver aussi le nombre de logs non joints ; aucune preuve inventée en cas de perte de logs.

Tests futurs : signal normal → aucune confirmation ; IP usurpée dans XFF → ignorée ; IP NAT commune → abstention ; journaux hors fenêtre → refus ; duplications de logs → déduplication request_id ; signal ML sans logs → REJECTED ; événement valide → décision traçable.
