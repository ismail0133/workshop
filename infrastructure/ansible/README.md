# Exécuteur Ansible à réaliser en phase 5

Contrôleur Linux en conteneur, utilisateur non-root, aucun socket Docker. Inventory localhost uniquement. Les futurs playbooks immuables `block_source.yml` et `remove_source_block.yml` utiliseront `ansible.builtin.uri` avec unix_socket vers le contrôleur du WAF. Aucun playbook exécutable n’est créé en phase 0.

Paramètres validés selon REMEDIATION_DESIGN : UUID action, IPv4 exacte autorisée, TTL 30..300 s, version et fencing token. Catalogue fermé, pas de nom de fichier fourni dans un job. Résultats bornés et expurgés de secrets. Faire un syntax-check puis tester idempotence et timeout sur les deux architectures avant démonstration.
