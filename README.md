# Actualización ActivoLab: tres perfiles de usuario v1

**Lee primero [Usuarios y permisos](docs/USUARIOS_Y_PERMISOS.md)** para instalar o actualizar sin perder registros. El administrador inicial utiliza APP_USERNAME / APP_PASSWORD solo al crear la tabla de cuentas; después se administran desde la web. La identidad se configura desde el menú Configuración.

# ActivoLab | Sistema de inventario de activos

Proyecto académico de Servidores II. Inventario genérico para almacenes, oficinas, talleres o áreas de TI, sin dependencia de ninguna empresa. Los registros precargados son ficticios. Es un prototipo de laboratorio, no una aplicación de producción.

## Funciones

- Inicio de sesión, alta y edición de activos individuales, búsqueda por código, descripción, serie o ubicación, filtros por tipo y estado.
- Baja lógica e historial de movimientos, datos persistentes en MySQL.
- Categorías ampliables desde el menú Categorías. Los tipos existentes se conservan.
- Códigos y series únicos de formato libre alfanumérico (también puntos, guiones y guiones bajos). No se exige prefijo. Para bienes sin serie asigna un identificador interno único.
- Identidad configurable mediante APP_NAME y ORG_NAME en `.env`.
- Git/GitHub, publicación de imagen en Docker Hub, GitHub Actions, respaldos y recuperación aislada.

## 1. Instalación nueva (Ubuntu Server o Debian)

Recomendado: 4 GB RAM, 2 vCPU y 20 GB de disco libre. Red de laboratorio y acceso a Internet para descargar dependencias e imágenes.

```bash
unzip Inventario_Tecnologico_Proyecto_Final.zip
cd Inventario_Tecnologico_Proyecto_Final
sudo bash scripts/instalar_requisitos_inventario.sh --deploy .
sudo docker compose ps
hostname -I
```

El instalador configura Docker/Compose si son necesarios, genera `.env` con credenciales de laboratorio cuando no existe, y espera la respuesta de `/health`. Usa `sudo nano .env` para consultar o editar el nombre y la organización, y obtener las credenciales `APP_USERNAME` y `APP_PASSWORD`. No cambies las credenciales de MySQL después de inicializar el volumen. Abre `http://IP_DE_TU_VM:8080` (o el puerto HTTP_PORT de `.env`). En una VM NAT configura reenvío de puertos; en red puente usa la IP de la VM. No expongas este prototipo a Internet.

## 2. Actualizar una instalación existente sin perder datos

Usa el ZIP `Inventario_Actualizacion_Generica.zip`, que contiene los archivos con rutas relativas a la raíz de tu proyecto actual. No contiene `.env`, respaldos ni datos privados. **No descomprimas el ZIP completo en otra carpeta para sustituir una instalación activa**.

En la carpeta del proyecto anterior, identifica el nombre Compose y el volumen existentes antes de sustituir los archivos:

```bash
sudo docker compose ls
sudo docker compose ps
sudo docker compose config --volumes
```

El nombre debe coincidir con el despliegue activo (en la edición anterior se llamaba `inventario-telecom-cfe` por defecto). Si ya tienes el script del avance 3, crea un respaldo ahora:

```bash
sudo bash scripts/respaldo.sh
```

Conserva una copia del `.env` y de tus fuentes fuera del repositorio antes de actualizar. Edita el `.env` existente con `sudo nano .env` y conserva todas las contraseñas y MYSQL_DATABASE. Agrega o actualiza las siguientes líneas (usa tu nombre de Compose real, no un nuevo nombre):

```dotenv
COMPOSE_PROJECT_NAME=inventario-telecom-cfe
APP_NAME="Inventario de Activos"
ORG_NAME="Almacen general"
```

Si ya existe `APP_IMAGE`, comenta esa línea temporalmente para construir la imagen genérica local. Guarda y descomprime la actualización **en la misma carpeta anterior**, sin cambiar su `.env`:

```bash
unzip -o ~/Inventario_Actualizacion_Generica.zip
sudo docker compose config -q
sudo docker compose ps
```

Confirma que aparecen los mismos servicios activos y no un proyecto vacío. Si no aparecen, detente y comprueba COMPOSE_PROJECT_NAME. No uses `down -v`. Genera otro respaldo antes de tocar catálogos, especialmente si no tenías el script de respaldo:

```bash
sudo bash scripts/respaldo.sh
sudo docker compose exec -T db sh -ec 'MYSQL_PWD="$MYSQL_PASSWORD" mysql -u "$MYSQL_USER" "$MYSQL_DATABASE"' < db/catalogos_genericos.sql
sudo docker compose up -d --build
sudo docker compose restart nginx
sudo docker compose ps
```

La sentencia de catálogo agrega los tipos genéricos faltantes sin modificar ni borrar los registros antiguos. Los equipos que ya registraste conservan sus códigos, estados y movimientos. Los seis ejemplos genéricos de `db/init.sql` solo se cargan en un volumen NUEVO. No se cambia ni renombra tu base de datos anterior: mantener el nombre del proyecto Compose y el volumen evita perder acceso a los datos.

## 3. Personalización

Ejemplos de identidad en `.env`:

```dotenv
APP_NAME="Control de inventario"
ORG_NAME="Taller de mantenimiento"
```

Aplica cambios de identidad con `sudo docker compose up -d --force-recreate app` y, para garantizar que Nginx resuelva el contenedor recreado, `sudo docker compose restart nginx`. No es necesario reiniciar MySQL.

El menú Categorías permite agregar tipos (p. ej., Herramienta manual, Cámara o Equipo médico). Las categorías ya asignadas a activos no se eliminan. Los estados mantienen el flujo: Disponible, Asignado, En mantenimiento, En reparación, Reservado y Baja.

El inventario registra unidades individuales, no cantidades agregadas ni ventas. Adapta cada categoría y ubicación a tu caso de estudio usando información ficticia.

## 4. Demostración

1. Ejecuta `sudo docker compose ps` y abre la web. Entra con las credenciales de `.env`.
2. Revisa los registros precargados (en una instalación nueva son seis: computadora, monitor, impresora, switch, taladro y silla).
3. Crea una categoría, por ejemplo `Cámara`, y registra un activo con código `INV-007`, serie `SN-DEMO-007`, descripción `Cámara de laboratorio`, estado Disponible y ubicación Almacén A1. Usa valores únicos si ya existen.
4. Busca el código, edita a Asignado, cambia ubicación y consulta el historial. Si procede, muestra la baja lógica.
5. Reinicia/recrea servicios sin eliminar el volumen y comprueba que el registro sigue guardado.

## 5. Avances 2 y 3

Sigue `docs/AVANCES_2_Y_3.md` para GitHub, Docker Hub, pruebas y respaldos. La imagen que publica `scripts/publicar_imagen.sh` se llama `USUARIO/inventario-activos:v1.0.0`. Las pruebas automatizadas de `.github/workflows/validacion.yml` usan instalaciones desechables y datos nuevos. No ejecutes `tests/integracion.py` contra tu inventario activo.

Respaldo y restauración aislada:

```bash
sudo bash scripts/respaldo.sh
sudo bash scripts/restaurar.sh backups/ARCHIVO.sql --prueba
```

Sustituye ARCHIVO por el nombre real. El modo de prueba no toca los datos originales. Guarda el SQL y su SHA-256 fuera del servidor; no los subas a GitHub.

## 6. Arquitectura y evidencias

Navegador → Nginx (8080 del anfitrión → 80 interno) → Flask/Gunicorn (5000 interno) → MySQL (3306 interno). La red bridge `red_inventario` conecta los tres servicios, y `db_data` conserva los datos. Consulta `docs/diagrama_arquitectura.md` y `docs/guion_presentacion.md`.

Captura la web, las categorías, los tres contenedores, los commits, la imagen en Docker Hub, las pruebas exitosas de Actions y la recuperación aislada. No muestres contraseñas ni presentes resultados no ejecutados como hechos.

## 7. Diagnóstico

```bash
sudo docker compose ps
sudo docker compose logs --tail=80 db app nginx
curl -fsS http://127.0.0.1:8080/health
```

Si no funciona, revisa el puerto, el acceso a MySQL y `.env`. Nunca ejecutes `docker compose down -v` sobre datos que quieres conservar. El proyecto está revisado estáticamente; verifica su ejecución real en tu VM y tus cuentas externas.
