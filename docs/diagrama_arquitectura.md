# Arquitectura del proyecto final

```mermaid
flowchart TB
    U[Usuario - login / inventario / formularios] -->|HTTP 8080| N[Nginx :80]
    subgraph R[red_inventario - Docker bridge]
        N -->|Proxy inverso| A[Flask / Gunicorn :5000]
        A -->|SQL interno :3306| D[(MySQL 8.4)]
    end
    D --- V[(Volumen persistente db_data)]
    I[db/init.sql - datos ficticios] -.->|Primera inicialización| D
    G[GitHub / Docker Hub] -.-> A
    T[GitHub Actions] -.-> A
    B[Respaldo y restauración] -.-> D
```

## Qué hace cada componente

- **Nginx** publica el único puerto accesible desde el equipo anfitrión (`HTTP_PORT=8080` hacia `:80`).
- **Flask** sirve el login, los filtros, los formularios de altas y ediciones, la baja lógica, el historial y la comprobación `/health`.
- **MySQL** utiliza cuatro tablas: `equipos`, `tipos_equipo`, `estados`, `movimientos`.
- **Volumen db_data** conserva el contenido de `/var/lib/mysql` aunque se reinicien o recreen los contenedores.
- **Red red_inventario** permite que `nginx`, `app` y `db` se comuniquen internamente. Los puertos 5000 y 3306 no se publican al anfitrión.
- **Operación del proyecto**: versionado/publicación de imagen, validación automática y respaldo/restauración.
