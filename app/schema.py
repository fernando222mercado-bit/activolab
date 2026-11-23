"""Migración aditiva, idempotente. Ejecutar antes de iniciar Gunicorn."""
import os
from werkzeug.security import generate_password_hash
from main import get_connection
from stock_schema import migrate_stock, repair_database, seed_demo


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK('activolab_schema_v2', 60) AS ok")
            if cur.fetchone()['ok'] != 1:
                raise RuntimeError('No se pudo bloquear la migración')
            try:
                cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(80) NOT NULL UNIQUE,
                    nombre VARCHAR(120) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    rol ENUM('admin','almacen','usuario') NOT NULL,
                    activo BOOLEAN NOT NULL DEFAULT TRUE,
                    version_sesion INT NOT NULL DEFAULT 1,
                    creado TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ultimo_acceso TIMESTAMP NULL DEFAULT NULL
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
                cur.execute('''CREATE TABLE IF NOT EXISTS accesos (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NULL,
                    username VARCHAR(80) NOT NULL,
                    evento ENUM('LOGIN_OK','LOGIN_FALLO','LOGOUT') NOT NULL,
                    ip VARCHAR(45) NOT NULL,
                    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_accesos_fecha (fecha),
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
                cur.execute('''CREATE TABLE IF NOT EXISTS configuracion (
                    id INT PRIMARY KEY, app_name VARCHAR(120) NOT NULL,
                    org_name VARCHAR(120) NOT NULL
                ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
                cur.execute('''SELECT COUNT(*) AS n FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='movimientos' AND COLUMN_NAME='actor' ''')
                if not cur.fetchone()['n']:
                    cur.execute('ALTER TABLE movimientos ADD COLUMN actor VARCHAR(80) NULL')
                cur.execute('INSERT IGNORE INTO configuracion (id, app_name, org_name) VALUES (1,%s,%s)',
                            (os.getenv('APP_NAME','Inventario de Activos')[:120], os.getenv('ORG_NAME','Organización de demostración')[:120]))
                cur.execute('SELECT COUNT(*) AS n FROM usuarios')
                if cur.fetchone()['n'] == 0:
                    user, password = os.environ['APP_USERNAME'], os.environ['APP_PASSWORD']
                    if not user.strip() or len(user)>80 or not password or len(password)>120:
                        raise RuntimeError('Credenciales iniciales inválidas en .env')
                    cur.execute('INSERT INTO usuarios (username,nombre,password_hash,rol) VALUES (%s,%s,%s,\'admin\')',
                                (user, 'Administrador inicial', generate_password_hash(password)))
                migrate_stock(cur)
                cur.execute("SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='demo_v3_pendiente'")
                if cur.fetchone()['n']:
                    cur.execute('SELECT pendiente FROM demo_v3_pendiente WHERE id=1')
                    marker=cur.fetchone()
                    if marker and marker['pendiente']:
                        seed_demo(cur)
                        cur.execute('UPDATE demo_v3_pendiente SET pendiente=0 WHERE id=1')
                conn.commit()
            finally:
                cur.execute("SELECT RELEASE_LOCK('activolab_schema_v2')")
    print('Esquema de usuarios y auditoría listo.', flush=True)

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 1:
        migrate()
    elif sys.argv[1:] in (['--repair-preview'], ['--repair-apply'], ['--demo']):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT GET_LOCK('activolab_schema_v2',60) AS ok")
                if cur.fetchone()['ok'] != 1:
                    raise RuntimeError('No se pudo bloquear la operación')
                try:
                    if sys.argv[1] == '--demo':
                        seed_demo(cur)
                        print('Datos ficticios cargados; registros previos conservados.')
                    else:
                        changed, skipped = repair_database(cur, sys.argv[1] == '--repair-apply')
                        print(f'Filas con texto reparable: {changed}; conflictos omitidos: {skipped}.')
                    conn.commit()
                finally:
                    cur.execute("SELECT RELEASE_LOCK('activolab_schema_v2')")
    else:
        raise SystemExit('Argumento desconocido')
