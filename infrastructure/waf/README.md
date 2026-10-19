# WAF prévu

Base candidate : image Nginx du projet officiel OWASP ModSecurity CRS. Le tag/digest multiarchitecture et l’image dérivée restent à tester/fixer ; aucun faux manifeste Dockerfile n’est fourni.

Image dérivée future : routes publiques explicites, TLS 8443, CRS, logs JSONL, métriques 9113 et adaptateur de contrôle Unix local. Socket partagé exclusivement avec remediation-runner. Contrat précis dans `docs/security/REMEDIATION_DESIGN.md`. Le besoin de cet adaptateur est inclus dans le planning et le budget ; la base officielle seule ne fournit pas la remédiation conçue.

Premier essai bloquant : deux machines du PA doivent produire deux IP sources distinctes dans les journaux. Ne jamais remplacer la source fiable par un X-Forwarded-For client.
