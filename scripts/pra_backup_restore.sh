#!/usr/bin/env bash
# PRA — sauvegarde PostgreSQL et VÉRIFICATION de restauration vers une instance DISTINCTE.
#
#   scripts/pra_backup_restore.sh backup  <dsn_source> <dossier>
#   scripts/pra_backup_restore.sh verify  <dsn_cible>  <dossier>   # restaure puis compare
#
# Prérequis : pg_dump, pg_restore, psql (client PostgreSQL 17 recommandé). Voir
# docs/runbooks/RECOVERY_RUNBOOK.md §6 pour l'exécution dans un conteneur attaché au réseau `data`.
# La cible doit être VIERGE (nouvelle instance/volume) avec les rôles déjà créés
# (python -m database.bootstrap). Aucune restauration destructive de la base de démonstration :
# ce script refuse de restaurer si la cible contient déjà des tables bancaires.
set -euo pipefail

SNAPSHOT_SQL="
SELECT json_build_object(
  'accounts',          (SELECT count(*) FROM bank.accounts),
  'transactions',      (SELECT count(*) FROM bank.transactions),
  'tx_success',        (SELECT count(*) FROM bank.transactions WHERE status = 'SUCCESS'),
  'sum_balance_minor', (SELECT coalesce(sum(balance_minor), 0) FROM bank.accounts),
  'accounts_digest',   (SELECT coalesce(md5(string_agg(id::text || ':' || balance_minor::text, ',' ORDER BY id)), '') FROM bank.accounts),
  'tx_digest',         (SELECT coalesce(md5(string_agg(id::text || ':' || status || ':' || amount_minor::text, ',' ORDER BY id)), '') FROM bank.transactions),
  'users',             (SELECT count(*) FROM auth.users),
  'schema_version',    (SELECT version_num FROM public.alembic_version LIMIT 1)
)::text"

now_ms() { echo $(( $(date +%s%N) / 1000000 )); }   # GNU date ; aucun Python requis (image postgres)

snapshot() { psql "$1" --no-psqlrc -XAtq -c "$SNAPSHOT_SQL"; }

cmd=${1:-}; dsn=${2:-}; dir=${3:-}
[ -n "$cmd" ] && [ -n "$dsn" ] && [ -n "$dir" ] || { sed -n '2,12p' "$0"; exit 2; }
mkdir -p "$dir"

case "$cmd" in
  backup)
    t0=$(now_ms)
    snapshot "$dsn" > "$dir/snapshot.json"        # état comptable AVANT sauvegarde
    pg_dump "$dsn" --format=custom --no-owner --no-privileges --file "$dir/resilience.dump"
    sha256sum "$dir/resilience.dump" | awk '{print $1}' > "$dir/resilience.dump.sha256"
    t1=$(now_ms)
    echo "backup OK  durée=$((t1 - t0)) ms  taille=$(wc -c < "$dir/resilience.dump") octets"
    echo "sha256=$(cat "$dir/resilience.dump.sha256")"
    cat "$dir/snapshot.json"
    ;;
  verify)
    [ "$(sha256sum "$dir/resilience.dump" | awk '{print $1}')" = "$(cat "$dir/resilience.dump.sha256")" ] \
      || { echo "ECHEC : empreinte de la sauvegarde invalide"; exit 1; }
    existing=$(psql "$dsn" --no-psqlrc -XAtq -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'bank'")
    [ "$existing" = "0" ] || { echo "REFUS : la cible contient déjà des tables bancaires"; exit 3; }
    t0=$(now_ms)
    # --no-owner/--no-privileges : les droits sont rejoués par la migration 0002_roles ci-dessous.
    pg_restore --dbname "$dsn" --no-owner --no-privileges --exit-on-error "$dir/resilience.dump"
    t1=$(now_ms)
    snapshot "$dsn" > "$dir/snapshot.restored.json"
    if cmp -s "$dir/snapshot.json" "$dir/snapshot.restored.json"; then
      echo "restauration OK  durée=$((t1 - t0)) ms  contrôle comptable : IDENTIQUE (soldes, transactions, empreintes)"
    else
      echo "ECHEC : contrôle comptable différent après restauration"
      echo "  avant   : $(cat "$dir/snapshot.json")"
      echo "  restauré: $(cat "$dir/snapshot.restored.json")"
      exit 1
    fi
    ;;
  *) echo "commande inconnue : $cmd"; exit 2 ;;
esac
