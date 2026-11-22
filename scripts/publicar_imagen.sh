#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
usuario=${1:-}; version=${2:-v1.0.0}
[[ "$usuario" =~ ^[a-z0-9][a-z0-9_-]+$ && "$version" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Uso: bash scripts/publicar_imagen.sh USUARIO_DOCKERHUB v1.0.0' >&2; exit 2; }
imagen="$usuario/inventario-activos:$version"
echo 'Inicia sesión en Docker Hub (usa token de acceso con permiso de escritura).'
docker login -u "$usuario"
docker build -t "$imagen" ./app
docker push "$imagen"
echo "Imagen publicada: $imagen"
