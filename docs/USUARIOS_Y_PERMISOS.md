# ActivoLab 2: usuarios y control de acceso

## Instalación sobre la versión genérica existente

1. En el servidor, entra a la carpeta del proyecto que funciona actualmente (la que contiene `compose.yaml` y `.env`).
2. Antes de actualizar, ejecuta `sudo bash scripts/respaldo.sh` y conserva el respaldo fuera del servidor si es posible.
3. Descomprime `ActivoLab_Actualizacion_Usuarios.zip` en esa misma carpeta con `unzip -o ~/ActivoLab_Actualizacion_Usuarios.zip`. La actualización no contiene `.env`, datos ni compose.yaml. Así conserva los parámetros del despliegue y el nombre del volumen.
4. Ejecuta `sudo docker compose config -q`, `sudo docker compose up -d --build --wait --wait-timeout 240` y `sudo docker compose restart nginx`. Si falla, consulta `sudo docker compose logs --tail=100 app db`.
5. Abre el inventario en su URL habitual. La primera vez se crea el administrador con APP_USERNAME y APP_PASSWORD del .env. La migración añade usuarios, accesos, configuración y actor en movimientos, sin borrar registros anteriores. Si ya existen usuarios, no se reinicializan.
6. Inicia sesión con ese administrador y entra a Usuarios. Crea las cuentas del jefe y del usuario normal tú mismo; usa contraseñas distintas de mínimo 10 caracteres. No se crean cuentas de prueba con contraseñas públicas.

## Instalación nueva

Descomprime ActivoLab_Usuarios_Proyecto_Final.zip, entra a su carpeta y ejecuta `sudo bash scripts/instalar_requisitos_inventario.sh --deploy .`. No ejecutes una instalación nueva en paralelo si el puerto o el nombre del proyecto Compose ya se utilizan.

## Permisos y demostración

- Administrador: altas, edición completa, bajas, categorías, historial, creación/edición/desactivación de cuentas, reinicio de contraseñas, accesos, configuración visible y contraseña propia. No puede desactivar ni degradar su cuenta actual.
- Jefe de almacén (`almacen`): consultar y filtrar, modificar ubicación, custodio y estado operativo de activos no dados de baja, ver historial. No puede crear activos, editar identificación ni dar de baja.
- Usuario normal (`usuario`): consulta y filtros, contraseña propia. No puede modificar inventario ni acceder a la bitácora.

Demuestra un alta con el administrador; crea un jefe y un lector. Desde otra ventana privada inicia sesión como jefe y cambia ubicación y responsable. Verifica que el historial registre su usuario. Con el lector, abre `/usuarios` o `/equipos/nuevo` y demuestra HTTP 403. Vuelve al administrador y consulta Accesos: se registran inicio correcto, fallo y cierre explícito, fecha y dirección IP observada. No se registran contraseñas. No equivale a monitoreo de sesiones en tiempo real.

## Operación y seguridad

- Las contraseñas de cuentas se guardan como hashes scrypt de Werkzeug. El .env sigue conteniendo los secretos originales del despliegue; protégelo. Cambiar APP_PASSWORD en .env no modifica una cuenta existente: usa Mi cuenta o Usuarios.
- Las rutas validan el rol y los POST usan CSRF. Se consulta la cuenta y su versión de sesión en cada solicitud protegida. Cambiar permisos, contraseña o desactivar una cuenta invalida sus sesiones anteriores.
- Los respaldos incluyen las tablas nuevas. Son sensibles (hashes, usuarios, registros de IP). No compartir ni subir a GitHub. Para restaurar un respaldo anterior a esta actualización, detén la aplicación, usa el procedimiento de recuperación de la versión anterior y vuelve a ejecutar la migración; no combines tablas antiguas y nuevas sin revisar consistencia. El modo de prueba actualizado espera un respaldo de esta versión.
- La bitácora muestra los 200 eventos más recientes. El historial conserva eventos antiguos sin actor identificado.
- Es un entorno académico HTTP de red controlada; para producción requiere TLS, limitación de intentos, política de retención, monitoreo y gestión segura de secretos.
- La configuración de nombre y organización se guarda en MySQL al editarla. APP_NAME y ORG_NAME del .env son únicamente valores iniciales después de la migración.

## CI y publicación

La prueba de integración en GitHub Actions crea cuentas ficticias, comprueba permisos en rutas GET y POST, cambios operativos, bitácora y desactivación, además de las pruebas anteriores. La ejecución de Docker y CI real debe hacerse en tu servidor/GitHub. Publica una versión nueva de la imagen con `sudo bash scripts/publicar_imagen.sh USUARIO_DOCKERHUB v2.0.0`.
