# Données fictives phase 1

`docker compose run --rm db-tools python -m database.seeds.demo` initialise Alice/Bob USER, OPERATOR, ADMIN et VALIDATOR. A=100000, B=50000 centimes EUR ; deux comptes synthétiques de 10000 centimes sont réservés au validateur. Les mots de passe générés localement sont hachés avec Argon2id. UUID stables et insertion idempotente : aucun solde ou mot de passe existant n’est réinitialisé.
