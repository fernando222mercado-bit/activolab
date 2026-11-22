#!/usr/bin/env bash
# Instalador de requisitos para Inventario de Activos (simulación académica).
# Ubuntu Server 22.04/24.04/26.04/26.10 o Debian 12/13, con systemd.
# Uso:
#   sudo bash instalar_requisitos_inventario.sh
#   sudo bash instalar_requisitos_inventario.sh --deploy /ruta/al/proyecto
#   sudo bash instalar_requisitos_inventario.sh --deploy .
set -Eeuo pipefail
umask 077

readonly SCRIPT_NAME="$(basename -- "$0")"
MODE="install"
PROJECT_DIR=""

info() { printf '\n\033[1;34m[INFO]\033[0m %s\n' "$*"; }
okay() { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[AVISO]\033[0m %s\n' "$*" >&2; }
die() { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; exit 1; }
usage() {
  cat <<EOF
Preparación del servidor Inventario de Activos

Uso:
  sudo bash ${SCRIPT_NAME}                         Instalar herramientas y Docker
  sudo bash ${SCRIPT_NAME} --deploy /ruta/proyecto  Instalar y arrancar inventario
  sudo bash ${SCRIPT_NAME} --deploy .               Arrancar desde carpeta actual
  bash ${SCRIPT_NAME} --help                       Mostrar ayuda

El despliegue conserva los archivos .env y los volúmenes Docker existentes.
No elimina bases de datos ni modifica el firewall. Requiere Internet.
EOF
}

while (($#)); do
  case "$1" in
    --deploy)
      MODE="deploy"
      if [[ $# -ge 2 && "$2" != -* ]]; then
        PROJECT_DIR="$2"
        shift
      fi
      ;;
    --install-only) MODE="install" ;;
    -h|--help) usage; exit 0 ;;
    *) die "Argumento no reconocido: $1. Usa --help." ;;
  esac
  shift
done

[[ $EUID -eq 0 ]] || die "Ejecuta con sudo: sudo bash ${SCRIPT_NAME}"
[[ -f /etc/os-release ]] || die "No se pudo detectar el sistema operativo."
# shellcheck source=/dev/null
. /etc/os-release
case "${ID:-}" in
  ubuntu)
    DISTRO="ubuntu"
    CODENAME="${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}"
    case "$CODENAME" in jammy|noble|resolute|stonking) ;; *) die "Ubuntu '$CODENAME' no está entre las versiones previstas. Comprueba compatibilidad en docs.docker.com." ;; esac
    ;;
  debian)
    DISTRO="debian"
    CODENAME="${VERSION_CODENAME:-}"
    case "$CODENAME" in bookworm|trixie) ;; *) die "Debian '$CODENAME' no es una versión prevista." ;; esac
    ;;
  *) die "Sistema ${PRETTY_NAME:-desconocido} no compatible con este instalador (Ubuntu/Debian)." ;;
esac
command -v apt-get >/dev/null 2>&1 || die "No se encontró apt-get."
command -v systemctl >/dev/null 2>&1 || die "Este instalador requiere systemd."

if [[ "$MODE" == "deploy" ]]; then
  if [[ -z "$PROJECT_DIR" ]]; then
    PROJECT_DIR="$PWD"
  fi
  [[ -d "$PROJECT_DIR" ]] || die "No existe la carpeta del proyecto: $PROJECT_DIR. Descomprime primero el ZIP."
  PROJECT_DIR="$(cd -- "$PROJECT_DIR" && pwd -P)"
  [[ -f "$PROJECT_DIR/compose.yaml" ]] || die "Falta compose.yaml en $PROJECT_DIR. Usa la carpeta raíz del proyecto, no scripts/."
  [[ -f "$PROJECT_DIR/.env.example" ]] || die "Falta .env.example en $PROJECT_DIR."
  [[ -f "$PROJECT_DIR/db/init.sql" && -f "$PROJECT_DIR/app/Dockerfile" ]] || die "Faltan archivos del inventario en $PROJECT_DIR."
fi

info "Sistema: ${PRETTY_NAME} | arquitectura: $(dpkg --print-architecture)"
ram_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)"
if [[ -n "$ram_kb" && "$ram_kb" -lt 3900000 ]]; then
  warn "Se recomiendan al menos 4 GB de RAM para la VM. Detectados aproximadamente $((ram_kb/1024)) MiB."
fi
free_kb="$(df -Pk /var/lib 2>/dev/null | awk 'NR==2 {print $4}')"
if [[ "$free_kb" =~ ^[0-9]+$ ]] && (( free_kb < 8*1024*1024 )); then
  warn "Quedan menos de 8 GiB libres en el disco que aloja /var/lib. MySQL e imágenes Docker podrían quedarse sin espacio."
fi

export DEBIAN_FRONTEND=noninteractive
info "Instalando herramientas del servidor..."
apt-get update
apt-get install -y ca-certificates curl git unzip openssl
okay "Herramientas base instaladas."

# Evita alterar instalaciones preexistentes con versiones compatibles.
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  info "Docker y Docker Compose ya están presentes; se conservará su instalación."
else
  info "Configurando repositorio oficial de Docker..."
  conflicts=()
  for pkg in docker.io docker-compose docker-compose-v2 docker-doc docker-buildx podman-docker containerd runc; do
    if dpkg-query -W -f='${db:Status-Abbrev}' "$pkg" 2>/dev/null | grep -q '^ii'; then
      conflicts+=("$pkg")
    fi
  done
  if ((${#conflicts[@]})); then
    die "Se encontraron paquetes que podrían entrar en conflicto: ${conflicts[*]}. No los eliminé para proteger otros contenedores. Revisa la guía oficial de Docker y retíralos solo si es seguro."
  fi

  install -m 0755 -d /etc/apt/keyrings
  curl --fail --silent --show-error --location --retry 3 \
    "https://download.docker.com/linux/${DISTRO}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod 0644 /etc/apt/keyrings/docker.asc
  cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/${DISTRO}
Suites: ${CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  chmod 0644 /etc/apt/sources.list.d/docker.sources
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  okay "Docker Engine, Buildx y Docker Compose instalados."
fi

info "Habilitando servicio Docker..."
systemctl enable --now docker
systemctl is-active --quiet docker || die "Docker no está activo. Revisa: sudo journalctl -u docker -n 100"
command -v docker >/dev/null 2>&1 || die "No se encontró el ejecutable docker."
docker compose version >/dev/null 2>&1 || die "No se encontró el plugin docker compose."
docker info >/dev/null 2>&1 || die "Docker está instalado pero no responde al daemon."
okay "Docker está activo."
printf 'Docker: '; docker --version
printf 'Compose: '; docker compose version
printf 'Git: '; git --version

if [[ "$MODE" == "install" ]]; then
  cat <<'EOF'

REQUISITOS LISTOS.
Para desplegar el proyecto:
  1) Descomprime Inventario_Tecnologico_Proyecto_Final.zip.
  2) Ejecuta con la carpeta raíz del proyecto:
     sudo bash instalar_requisitos_inventario.sh --deploy /ruta/al/Inventario_Tecnologico_Proyecto_Final

Flask y MySQL se instalan dentro de los contenedores al ejecutar Compose.
No se añadió ningún usuario al grupo docker (equivale a permisos de root).
EOF
  exit 0
fi

info "Preparando inventario en: $PROJECT_DIR"
cd -- "$PROJECT_DIR"
if [[ -e .env ]]; then
  [[ -f .env ]] || die ".env existe pero no es un archivo regular."
  if grep -Eq '^(MYSQL_ROOT_PASSWORD|MYSQL_PASSWORD|APP_PASSWORD|FLASK_SECRET_KEY)=CAMBIAR_' .env; then
    die "El .env existente conserva claves de ejemplo. Edita esas claves con nano .env antes de desplegar. No las sobrescribí."
  fi
  info "Se conserva el .env existente (y sus credenciales)."
else
  cp -- .env.example .env
  mysql_root="$(openssl rand -hex 20)"
  mysql_pass="$(openssl rand -hex 20)"
  login_pass="$(openssl rand -hex 12)"
  flask_secret="$(openssl rand -hex 32)"
  sed -i \
    -e "s/^MYSQL_ROOT_PASSWORD=.*/MYSQL_ROOT_PASSWORD=${mysql_root}/" \
    -e "s/^MYSQL_PASSWORD=.*/MYSQL_PASSWORD=${mysql_pass}/" \
    -e 's/^APP_USERNAME=.*/APP_USERNAME=demo/' \
    -e "s/^APP_PASSWORD=.*/APP_PASSWORD=${login_pass}/" \
    -e "s/^FLASK_SECRET_KEY=.*/FLASK_SECRET_KEY=${flask_secret}/" .env
  # Dejar el archivo editable al usuario que posea el directorio del proyecto.
  chown --reference=. .env
  chmod 0600 .env
  okay "Se creó .env con contraseñas aleatorias (no se publican ni se sobrescriben en ejecuciones posteriores)."
  printf '\n  USUARIO WEB:   demo\n  CONTRASEÑA WEB: %s\n' "$login_pass"
  warn "Guarda esta contraseña en un lugar seguro. No muestres el .env durante la exposición."
fi

info "Validando Docker Compose..."
docker compose config -q
info "Construyendo e iniciando nginx + app + db..."
if ! docker compose up -d --build; then
  docker compose ps || true
  docker compose logs --tail=80 db app nginx || true
  die "Falló el despliegue. Comprueba conexión a Internet, espacio y registros de los servicios."
fi

info "Comprobando disponibilidad HTTP en la propia VM..."
http_port="$(sed -n -E 's/^HTTP_PORT=([0-9]+)$/\1/p' .env | tail -n 1)"
http_port="${http_port:-8080}"
[[ "$http_port" =~ ^[0-9]+$ ]] && ((http_port >= 1 && http_port <= 65535)) || die "HTTP_PORT debe ser un puerto numérico entre 1 y 65535."
ready=0
for _ in $(seq 1 75); do
  if curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${http_port}/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done

docker compose ps
if ((ready == 0)); then
  docker compose logs --tail=80 db app nginx || true
  die "No hubo respuesta saludable en http://127.0.0.1:${http_port}/health. Revisa los logs anteriores."
fi
okay "Inventario y base de datos responden correctamente."

printf '\nPrueba local: http://127.0.0.1:%s\n' "$http_port"
if command -v hostname >/dev/null 2>&1; then
  printf 'IPs de la VM: '
  hostname -I 2>/dev/null || true
fi
cat <<EOF

Desde tu computadora en red puente abre:
  http://IP_DE_TU_VM:${http_port}

Comprueba el inventario desde la carpeta del proyecto:
  sudo docker compose ps
  sudo bash scripts/verificar_avance1.sh ${http_port}

NOTAS:
  - No ejecutes 'docker compose down -v': elimina los datos persistentes.
  - Si ya había un volumen MySQL, mantén el mismo MYSQL_USER,
    MYSQL_DATABASE y MYSQL_PASSWORD del despliegue original.
  - Los puertos publicados por Docker pueden evitar algunas reglas UFW.
    Usa este prototipo solo en una red de laboratorio, nunca en Internet.
EOF
