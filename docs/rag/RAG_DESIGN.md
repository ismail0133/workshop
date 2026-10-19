# Assistant documentaire local

EPSI p.5 : Ollama + LangChain + RAG obligatoires, modèle local ≤8 milliards de paramètres. Choix : `qwen2.5:1.5b` (1.54B, Q4_K_M, fichier annoncé 986 MB), contexte volontairement limité à 2048 tokens, sortie max 384, température 0.1. Source : [fiche officielle Ollama](https://ollama.com/library/qwen2.5:1.5b). Budget de fonctionnement 3 GiB à mesurer, distinct de la taille du fichier.

Embeddings : `nomic-embed-text:v1.5`, annoncé 274 MB, via `/api/embed`. Source : [Ollama](https://ollama.com/library/nomic-embed-text). Ce modèle doit être évalué sur notre documentation française ; sa seule disponibilité ne garantit pas la qualité de recherche. Cible : au moins 8 bonnes références sur 10 questions de recette. Si insuffisant, sélectionner un embedding multilingue compatible et reconstruire entièrement l’index avant le test final ; pas de mélange de dimensions/modèles.

LangChain orchestre chargement, découpage, retrieval et prompt ; FAISS CPU en mémoire stocke les vecteurs. Pas de serveur vectoriel supplémentaire. RAG et FAISS restent sur PC Hôte même si Ollama est déporté. Sur Mac, Ollama natif est le choix de développement ; conteneur CPU ou PC IA sur Windows. Limiter à une génération et un modèle chargé simultanément ; indexer avant la démonstration pour éviter concurrence embeddings/LLM.

## Corpus et ingestion

Liste blanche : architecture, catalogue, contrats, runbooks de reprise, SC-01, PCA/PRA, limites connues et résultats d’essais validés. Exclure .env, secrets, clés, données utilisateurs, logs bruts, dumps SQL et documents d’entreprise/campus confidentiels. Le sujet EPSI n’est pas nécessaire à l’assistant d’exploitation. Documentation versionnée ; index construit par tâche hors requête, hash du corpus et du modèle dans manifest.json.

Découper par titres Markdown, chunks ≈350 tokens, overlap 50 ; conserver document_id, path relatif autorisé, section, chunk_id, sha256. Retirer les artefacts et liens externes non pertinents ; ne jamais exécuter un fragment du corpus. Vecteurs normalisés, FAISS IndexFlatIP, top-k=3. Si score insuffisant (seuil à calibrer sur 10 questions), réponse d’abstention. Persister index natif FAISS et métadonnées JSON ; pas de `allow_dangerous_deserialization` ni pickle non fiable.

Budget prompt 2048 : instructions ~250, question max ~400, contexte ≤900, réponse 384, marge ~114. Tronquer par chunks complets, pas par fragments sans source. Citations doivent correspondre aux chunks effectivement récupérés. Le modèle ne choisit pas de chemin arbitraire à lire.

## Génération et sécurité

Prompt système : répondre en français à partir du contexte fourni, citer les sections, distinguer faits et limites, s’abstenir si absent. Le texte utilisateur et les documents sont des données non fiables ; leurs demandes d’ignorer les règles ou d’exécuter des commandes n’accordent aucun droit. Aucun tool shell, endpoint runner, accès DB ou secret administratif n’est monté dans rag-service. React rend la réponse comme texte/Markdown sûr, jamais HTML brut.

Contrat réponse : answer, citations[{document_id,path,section,chunk_id,sha256}], grounded, model, index_version, request_id. grounded signifie appui documentaire contrôlé, pas certitude absolue ; le service valide la présence réelle des citations. Pas d’historique persistant en phase initiale. Timeout total 30 s, quota 1 génération, 429 si occupé. Index absent/Ollama indisponible → 503 ; réponse sans référence pertinente → abstention 200.

## Recette future

10 questions documentaires dont procédure RECOVERY_FAILED, limites SC-01, rôle WAF, RTO, permissions ; vérifier références et fidélité. Ajouter 3 questions hors corpus et 3 tentatives de prompt injection : abstention ou réponse documentaire, aucune action privilégiée. Mesurer RAM pic et temps p95 pendant la chaîne de reprise. Aucun test effectué en phase 0.
