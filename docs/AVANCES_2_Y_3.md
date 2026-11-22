# Inventario de Activos | Avances 2 y 3

Simulación académica. No hay datos o conexiones institucionales.

## 0. Instalación y actualización

Consulta el README principal. Para instalaciones anteriores, conserva el nombre de Compose, el `.env`, el volumen y las credenciales existentes. Para instalaciones nuevas utiliza el ZIP completo y ejecuta el instalador. Los datos de ejemplo son ficticios.

## 1. Avance 2: control de versiones

Crea un repositorio vacío en GitHub (sin README, licencia ni .gitignore iniciales). Puede ser privado. Usa tu cuenta y sustituye USUARIO por tu usuario de GitHub. Ejecuta desde la raíz del proyecto como tu usuario normal (no sudo):

```bash
git init
git branch -M main
git config user.name "Tu nombre"
git config user.email "Tu correo de GitHub"
git check-ignore .env backups/ejemplo.sql
git add .
git status --short
```

Revisa que `.env`, `backups/` y credenciales no aparezcan como staged. Si ya existe un repositorio, no lo reinicialices ni cambies su remoto sin revisar `git remote -v`. Si es nuevo:

```bash
git commit -m "Inventario funcional, validacion y recuperacion"
git remote add origin https://github.com/USUARIO/inventario-activos.git
git push -u origin main
```

Para autenticarte por HTTPS, usa el mecanismo de autenticación de GitHub o un token con acceso al repositorio, no la contraseña de tu cuenta. Nunca lo pegues en el URL remoto ni en el código. Para demostrar un segundo cambio real, edita la documentación de tu equipo, `git add docs/AVANCES_2_Y_3.md`, `git commit -m "Documentar pruebas del equipo"`, `git push`. Enseña `git log --oneline` y el repositorio. Si ya tienes commits, conserva su historial; no hagas push forzado.

## 2. Avance 2: Docker Hub

Crea una cuenta y un repositorio llamado `inventario-activos` en Docker Hub. Para una demostración académica puedes elegir público si el código solo contiene datos ficticios y no secretos. Genera un token de escritura. Desde la raíz:

```bash
sudo bash scripts/publicar_imagen.sh USUARIO_DOCKERHUB v1.0.0
```

El script solicita iniciar sesión, construye `./app`, etiqueta y publica la imagen. El token se introduce como contraseña cuando Docker lo solicite. No uses contraseña o token en argumentos. La imagen contiene el código de Flask, no la base de datos ni las credenciales `.env`. Cierra la sesión del registro después de usarla con `sudo docker logout` si no requieres acceso posterior a una imagen privada.

Para demostrar descarga y uso, añade o modifica la línea `APP_IMAGE=USUARIO_DOCKERHUB/inventario-activos:v1.0.0` en `.env` (sin cambiar ninguna otra variable). Después:

```bash
sudo docker compose pull app
sudo docker compose up -d --no-build
sudo docker compose restart nginx
sudo docker compose ps
sudo docker compose images
curl -fsS http://localhost:8080/health
```

Si el repositorio es privado debes estar autenticado. Si tu puerto no es 8080, usa el valor de HTTP_PORT. Para volver a la compilación local, elimina APP_IMAGE de `.env`, y ejecuta `sudo docker compose up -d --build`. Si compartes el proyecto en una arquitectura distinta (por ejemplo ARM64), construye/publica una imagen para esa plataforma o usa compilación local.

Evidencias: repositorio GitHub, commits, página Docker Hub con etiqueta v1.0.0 y `docker compose images`.

## 3. Avance 3: GitHub Actions

El archivo `.github/workflows/validacion.yml` ya está implementado. Al subirlo a la rama `main`, se ejecuta automáticamente (también en pull requests y manualmente desde Actions). No necesita secretos de Docker Hub: la publicación se realiza en el avance 2 desde el servidor. La validación usa contraseñas ficticias exclusivas del runner y una base nueva independiente.

En GitHub: repositorio > Actions > Validacion del inventario > ejecución > validar. Si Actions está deshabilitado, actívalo en Settings > Actions > General. La ejecución comprueba sintaxis Python/Bash, Compose, arranque, `/health`, inicio de sesión, alta, búsqueda, rechazo de duplicados, edición, baja lógica, historial, persistencia tras recrear contenedores, respaldo y restauración aislada. La limpieza `down -v` ocurre únicamente en el runner desechable. No ejecutes `tests/integracion.py` en tu inventario actual: crea y modifica registros de prueba.

Evidencias: captura de la ejecución y de los pasos realmente completados. Si falla, abre el paso rojo y revisa el error; no presentes una ejecución fallida como éxito.

## 4. Avance 3: respaldo de MySQL

Desde la raíz de tu proyecto en Ubuntu:

```bash
sudo bash scripts/respaldo.sh
sudo ls -lh backups/
```

Se genera un archivo `.sql` con las tablas y su contenido, y un archivo `.sha256` para comprobar integridad. Guarda ambos juntos, fuera del servidor también si puedes. El respaldo no contiene las cuentas del servidor MySQL ni reemplaza el `.env`. No publiques respaldos ni datos en GitHub.

## 5. Avance 3: recuperar sin arriesgar tu inventario

Crea un equipo ficticio en la web y genera un respaldo. Sustituye ARCHIVO por el nombre SQL real que imprimió el script:

```bash
sudo bash scripts/restaurar.sh backups/ARCHIVO.sql --prueba
```

El script verifica SHA-256, crea un contenedor MySQL temporal sin red, carga los datos en `inventario_prueba`, muestra las cantidades y los códigos recuperados y elimina el contenedor temporal y su volumen anónimo. No modifica la BD activa. Captura la salida antes de cerrar la terminal. Comprueba el equipo en la web original.

Solo si de verdad necesitas sobrescribir el inventario activo y entiendes las consecuencias, usa `--aplicar` en lugar de `--prueba`. El script solicita escribir RESTAURAR, detiene app y nginx, genera otro respaldo preventivo, importa el SQL y reinicia los servicios al finalizar correctamente. No es una restauración atómica: si falla, la base puede quedar parcialmente restaurada y app/nginx quedan detenidos; corrige el motivo y restaura el respaldo preventivo. No importes SQL de terceros. Utiliza `--prueba` para exponer, no `--aplicar`.

## 6. Presentación final (6-8 minutos)

1. Explicar la necesidad y arquitectura: navegador -> Nginx :8080 -> Flask :5000 -> MySQL :3306, volumen db_data.
2. Mostrar `sudo docker compose ps` y la interfaz web. Crear o editar equipo ficticio y enseñar historial.
3. Mostrar GitHub, commits y Docker Hub con la versión publicada. Mostrar `docker compose images`.
4. Mostrar el workflow y los resultados reales de GitHub Actions.
5. Crear respaldo con `respaldo.sh` y recuperar con `restaurar.sh --prueba`. Comparar el código del equipo y los registros.
6. Cerrar con objetivos alcanzados, limitaciones y plan B (VM local, ZIP, capturas y respaldo).

## 7. Evidencias para el documento de cierre

| Requisito | Evidencia que debes capturar | Resultado real |
|---|---|---|
| Adaptación del inventario | Web y registro ficticio | Completar |
| Infraestructura | Compose ps y arquitectura | Completar |
| Git | Historial de commits | Completar |
| Docker Hub | Imagen/tag y descarga | Completar |
| Validación | Actions y logs de pasos | Completar |
| Respaldo | SQL, tamaño y checksum | Completar |
| Recuperación | Listado de equipo restaurado | Completar |

El código de estos avances está preparado y revisado estáticamente; los resultados reales de Docker, GitHub y Docker Hub requieren ejecutarse con tu servidor y tus cuentas. No hay promesa de una ejecución remota ya realizada.
