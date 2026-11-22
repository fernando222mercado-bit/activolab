#!/usr/bin/env bash
set -euo pipefail
PORT="${1:-8080}"
echo '1) Validación Compose'
docker compose config -q
echo '2) Estado de contenedores'
docker compose ps
echo '3) Estado HTTP de Flask y MySQL'
curl -fsS "http://127.0.0.1:${PORT}/health"
echo
echo '4) Verificación de datos en MySQL'
docker compose exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE" -e "SELECT COUNT(*) AS equipos FROM equipos; SELECT COUNT(*) AS movimientos FROM movimientos;"'
echo '5) Listo: abre la web e inicia sesión para registrar, editar y dar de baja equipos.'
