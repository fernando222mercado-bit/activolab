#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p backups
archivo="backups/inventario_$(date -u +%Y%m%d_%H%M%S)_$$.sql"
tmp=$(mktemp backups/.respaldo.XXXXXX)
trap 'rm -f -- "$tmp"' EXIT
docker compose exec -T db sh -ec 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysqldump -u root --single-transaction --quick --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"' > "$tmp"
test -s "$tmp"
grep -q '^-- Dump completed on' "$tmp"
mv -- "$tmp" "$archivo"
sha256sum "$archivo" > "$archivo.sha256"
printf 'Respaldo listo: %s\n' "$archivo" >&2
printf '%s\n' "$archivo"
