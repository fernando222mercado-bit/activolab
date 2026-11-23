# Guion para demostrar el avance 1 funcional (5 a 7 minutos)

**Importante:** el inventario es una simulación académica. Todos los códigos, ubicaciones, equipos y responsables de la demostración son ficticios.

1. **Objetivo y arquitectura (1 minuto)**. Mostrar `docs/diagrama_arquitectura.md`. Nginx atiende la web por el puerto 8080; Flask implementa las funciones del inventario en el puerto interno 5000; MySQL almacena los equipos por el puerto interno 3306; `db_data` conserva los registros.
2. **Estado de los servicios (40 segundos)**. Ejecutar `sudo docker compose ps` y enseñar `nginx`, `app` y `db` activos; `app` y `db` en estado `healthy`.
3. **Inicio de sesión (20 segundos)**. Abrir `http://IP_VM:8080`; iniciar sesión con la cuenta de demostración definida en `.env`. No enseñar la contraseña ni el archivo `.env` al público.
4. **Consulta y búsqueda (50 segundos)**. Mostrar grupos de activos y consumibles ficticios, filtrar por `Monitor`, buscar `INV-001` y limpiar filtros.
5. **Alta de un equipo (1 minuto)**. Ir a `Nuevo equipo` y registrar código `INV-007`, serie `SN-DEMO-007`, descripción `Monitor de 27 pulgadas`, tipo `Monitor`, estado `Disponible`, ubicación `Almacén / Estante A4`.
6. **Edición (45 segundos)**. Editar `INV-007`, cambiar el estado a `Asignado` y la ubicación a `Sala de pruebas`. Guardar y mostrar los nuevos valores.
7. **Historial (40 segundos)**. Abrir `Historial` y comprobar eventos `ALTA` y `ACTUALIZACION`. Opcionalmente dar de baja el equipo y mostrar el evento `BAJA`.
8. **Persistencia (1 minuto)**. Ejecutar `sudo docker compose restart`, esperar que los servicios indiquen `healthy` y recargar la web. El equipo agregado permanece en MySQL.
9. **Cierre (20 segundos)**. Explicar que el siguiente avance abordará publicación de imagen en Docker Hub y automatización en GitHub Actions; el tercer avance agregará pruebas automatizadas y respaldos/restauración.

## Capturas recomendadas

- Docker Compose con los tres servicios.
- Dashboard con grupos de activos y existencias de consumibles.
- Nuevo equipo registrado.
- Equipo editado y estado actualizado.
- Historial con ALTA y ACTUALIZACION.
- Dashboard después del reinicio, con los datos conservados.
