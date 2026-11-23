#!/usr/bin/env bash
# Ejecutar en la carpeta de la instalación ACTIVA, después de extraer el parche.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ -f .env ]] || { echo 'No existe .env. Para instalación nueva usa instalar_requisitos_inventario.sh.' >&2; exit 1; }
docker compose config -q
[[ -n "$(docker compose ps --status running -q db)" ]] || { echo 'No se encontró la base activa. Revisa COMPOSE_PROJECT_NAME; no se creará otro volumen.' >&2; exit 1; }
# No compilar sobre una etiqueta de Docker Hub configurada anteriormente.
image=$(docker compose config --format json | python3 -c 'import sys,json; print(json.load(sys.stdin)["services"]["app"]["image"])')
[[ "$image" == 'inventario-activos:local' ]] || { echo 'Comenta APP_IMAGE en .env (o elimina la variable exportada) antes de actualizar.' >&2; exit 1; }
echo 'Deteniendo escrituras de la aplicación para respaldar los datos.'
docker compose stop nginx app
bash scripts/respaldo.sh
docker compose up -d --build --wait --wait-timeout 240 db app
# Reparación de secuencias dañadas conocidas, sin cambiar credenciales ni IDs.
docker compose exec -T app python schema.py --repair-preview
docker compose exec -T app python schema.py --repair-apply
# Datos ficticios a petición, una sola carga; --sin-demo omite la carga.
if [[ "${1:-}" != '--sin-demo' ]]; then
  docker compose exec -T app python schema.py --demo
fi
docker compose up -d --wait --wait-timeout 120 nginx
docker compose restart nginx
docker compose ps
echo 'Actualización v3 aplicada. Revisa los servicios y el inventario en el navegador.'
