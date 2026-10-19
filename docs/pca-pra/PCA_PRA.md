# PCA / PRA — conception initiale

Service critique : paiements fictifs corrects. Dépendances essentielles : WAF, auth pour nouveaux tokens, Payment API, Postgres. Détection/reprise : Prometheus/Loki/ML/Incident/runner ; RAG ne doit pas empêcher la reprise. Responsable coordination : rôle gouvernance/intégration ; responsables techniques dans IMPLEMENTATION_PLAN, noms à confirmer.

PCA SC-01 : préserver clients légitimes par filtrage de source autorisée, maintenir supervision et DB sous quotas ; aucune intervention corrective humaine dans chaîne nominale. Pas de fonctionnement hors ligne bancaire ni de paiement optimiste si DB indisponible. Les requêtes échouées sont explicitement signalées avec clé de retry ; ne jamais afficher succès avant commit.

PRA nominal : DETECTED→analyse→politique→action WAF→validation réelle→RECOVERED. Runbook détaillé dans `docs/security/REMEDIATION_DESIGN.md`. Si preuves insuffisantes, REJECTED ; si action/reprise échoue, RECOVERY_FAILED avec journal, arrêt de charge si sécurité l’exige, analyse par équipe hors preuve zéro-touch.

Objectif expérimental SC-01 : RTO≤60 s depuis première dégradation jusqu’au paiement de validation ; viser≤50 s nominal pour vidéo. RPO=0 transaction confirmée perdue dans SC-01, car aucune restauration DB ni suppression volume. Mesurer avant/après ids et conservation des soldes. Ce RPO ne couvre pas perte disque, corruption DB ou catastrophe hôte.

PRA hors scénario : sauvegarde PostgreSQL avant séance, test de restauration vers volume **distinct** en phase 9, contrôle comptable puis bascule documentée ; aucune restauration destructive automatique. Objectifs provisoires RTO30 min / RPO dernier backup, à calibrer ; non démontrés et exclus du claim SC-01. Ne jamais utiliser un redémarrage comme correction d’une compromission.

Retour à normale : contrôler fin de charge, expiration TTL120 s, absence de rechute, export des preuves, restitution des ressources ; préparer données uniquement entre essais. Critères abandon : sortie périmètre, débit non borné, mauvaise cible, corruption, action inconnue. Coach averti si dépassement autorisation. Une intervention humaine corrective est conservée dans le bilan et invalide le succès autonome de cet essai.

Livrable de test : chronologie t0 dégradation/t1 détection/t2 action/t3 validation, incident/action/transaction, config/modèle, résultat, RTO, pertes constatées et limites. L’équipe révise les objectifs avec le coach après trois répétitions sur PC Hôte.
