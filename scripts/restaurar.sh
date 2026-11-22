#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
archivo=${1:-}
modo=${2:---prueba}
[[ -n "$archivo" && -f "$archivo" && -s "$archivo" ]] || { echo 'Uso: bash scripts/restaurar.sh backups/archivo.sql [--prueba|--aplicar]' >&2; exit 2; }
[[ "$modo" == --prueba || "$modo" == --aplicar ]] || exit 2
if [[ -f "$archivo.sha256" ]]; then
  sha256sum -c "$archivo.sha256" >&2
else
  echo 'Se requiere el archivo .sha256 creado por respaldo.sh.' >&2; exit 2
fi
# Solo importes respaldos propios de confianza. El modo de prueba NO escribe en la BD activa.
if [[ "$modo" == --prueba ]]; then
  # Servidor MySQL temporal e independiente, sin puerto ni acceso a la red del inventario.
  nombre="inventario-restauracion-$(date +%s)-$$"
  clave=$(openssl rand -hex 24)
  docker run -d --name "$nombre" --network none -e MYSQL_ROOT_PASSWORD="$clave" -e MYSQL_DATABASE=inventario_prueba mysql:8.4 >/dev/null
  trap 'docker rm -fv "$nombre" >/dev/null 2>&1 || true' EXIT
  listo=0
  for ((i=0;i<120;i++)); do
    if docker exec "$nombre" sh -ec 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -h 127.0.0.1 -u root -Nse "SELECT 1"' >/dev/null 2>&1; then listo=1; break; fi
    sleep 2
  done
  [[ "$listo" == 1 ]] || { docker logs --tail=50 "$nombre" >&2; echo "MySQL temporal no está listo." >&2; exit 1; }
  docker exec -i "$nombre" sh -ec 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -u root inventario_prueba' < "$archivo"
  docker exec "$nombre" sh -ec 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root inventario_prueba -e "SELECT COUNT(*) AS equipos_recuperados FROM equipos; SELECT COUNT(*) AS movimientos_recuperados FROM movimientos; SELECT codigo_inventario, descripcion FROM equipos ORDER BY id; SELECT COUNT(*) AS cuentas_recuperadas FROM usuarios; SELECT COUNT(*) AS accesos_recuperados FROM accesos;"'
  echo 'Restauración de prueba correcta. La base activa no se modificó.'
else
  echo 'ATENCIÓN: se sobrescribirán las tablas activas con el respaldo seleccionado.'
  read -r -p 'Escribe RESTAURAR para confirmar: ' confirmar
  [[ "$confirmar" == RESTAURAR ]] || { echo 'Cancelado.'; exit 1; }
  docker compose stop nginx app
  echo 'Servicios detenidos. Si falla el proceso, permanecerán detenidos para permitir recuperación.'
  seguridad=$(bash scripts/respaldo.sh)
  echo "Respaldo previo: $seguridad"
  docker compose exec -T db sh -ec 'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; exec mysql -u root "$MYSQL_DATABASE"' < "$archivo"
  docker compose exec -T db sh -ec 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -u root "$MYSQL_DATABASE" -e "SELECT COUNT(*) AS equipos_recuperados FROM equipos; SELECT COUNT(*) AS movimientos_recuperados FROM movimientos;"'
  docker compose up -d --no-build app nginx
  echo 'Restauración aplicada. Comprueba /health y el inventario.'
fi
