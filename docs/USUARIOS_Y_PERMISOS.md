# ActivoLab 2: usuarios y control de acceso

## Instalación y actualización

Sigue [Actualización v3](ACTUALIZACION_V3.md). Se mantienen las cuentas existentes y los permisos de v2.

## Permisos y demostración

- Administrador: altas individuales o masivas, alta de consumibles, mínimos, edición completa, bajas, categorías, historial, creación/edición/desactivación de cuentas, reinicio de contraseñas, accesos, configuración visible y contraseña propia. No puede desactivar ni degradar su cuenta actual.
- Jefe de almacén (`almacen`): consultar y filtrar, modificar ubicación, custodio y estado operativo de activos no dados de baja, registrar entradas y salidas de consumibles, ver historial. No puede crear activos, editar identificación ni dar de baja.
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

La prueba de integración en GitHub Actions crea cuentas ficticias, comprueba permisos en rutas GET y POST, cambios operativos, bitácora y desactivación, además de las pruebas anteriores. La ejecución de Docker y CI real debe hacerse en tu servidor/GitHub. Publica una versión nueva de la imagen con `sudo bash scripts/publicar_imagen.sh USUARIO_DOCKERHUB v3.0.0`.
