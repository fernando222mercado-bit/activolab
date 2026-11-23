"""Migración aditiva para consumibles, mínimos y datos de demostración."""
from inventory import repair_text


def migrate_stock(cur):
    cur.execute('''CREATE TABLE IF NOT EXISTS consumibles (
        id INT AUTO_INCREMENT PRIMARY KEY, sku VARCHAR(30) NOT NULL UNIQUE,
        descripcion VARCHAR(180) NOT NULL, tipo_id INT NOT NULL,
        ubicacion VARCHAR(120) NOT NULL, cantidad INT UNSIGNED NOT NULL DEFAULT 0,
        minimo INT UNSIGNED NOT NULL DEFAULT 0,
        FOREIGN KEY (tipo_id) REFERENCES tipos_equipo(id)
    ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
    cur.execute('''CREATE TABLE IF NOT EXISTS movimientos_consumibles (
        id BIGINT AUTO_INCREMENT PRIMARY KEY, consumible_id INT NOT NULL,
        accion ENUM('ENTRADA','SALIDA','ALTA') NOT NULL,
        cantidad INT UNSIGNED NOT NULL, saldo INT UNSIGNED NOT NULL,
        motivo VARCHAR(180) NOT NULL, actor VARCHAR(80) NOT NULL,
        fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (consumible_id) REFERENCES consumibles(id)
    ) ENGINE=InnoDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci''')
    cur.execute('''CREATE TABLE IF NOT EXISTS demo_v3_cargado (id INT PRIMARY KEY) ENGINE=InnoDB''')
    cur.execute('''CREATE TABLE IF NOT EXISTS minimos_activos (
        clave CHAR(64) PRIMARY KEY, minimo INT UNSIGNED NOT NULL DEFAULT 0
    ) ENGINE=InnoDB''')


def repair_database(cur, apply=False):
    # No toca códigos, series, usuarios de acceso, contraseñas ni roles.
    fields = {'equipos': ('descripcion','marca','modelo','ubicacion','responsable'),
              'tipos_equipo': ('nombre',), 'estados': ('nombre',),
              'movimientos': ('estado_anterior','estado_nuevo','ubicacion_anterior','ubicacion_nueva'),
              'usuarios': ('nombre',), 'configuracion': ('app_name','org_name'),
              'consumibles': ('descripcion','ubicacion'), 'movimientos_consumibles': ('motivo',)}
    changed = skipped = 0
    for table, cols in fields.items():
        cur.execute(f'SELECT id,{",".join(cols)} FROM {table}')
        for row in cur.fetchall():
            changes = {col: repair_text(row[col]) for col in cols if repair_text(row[col]) != row[col]}
            if not changes:
                continue
            # Evita colisiones en catálogos con restricciones UNIQUE.
            if table in ('tipos_equipo','estados'):
                cur.execute(f'SELECT id FROM {table} WHERE nombre=%s AND id<>%s', (changes['nombre'],row['id']))
                if cur.fetchone():
                    skipped += 1
                    print(f'Omitido por nombre duplicado: {table} id={row["id"]}', flush=True)
                    continue
            changed += 1
            if apply:
                assignments = ','.join(f'{col}=%s' for col in changes)
                cur.execute(f'UPDATE {table} SET {assignments} WHERE id=%s', (*changes.values(),row['id']))
    return changed, skipped


def seed_demo(cur):
    """Códigos reservados DEMO3; no pisa ni repone unidades existentes."""
    cur.execute('SELECT id FROM demo_v3_cargado WHERE id=1')
    if cur.fetchone():
        return
    cur.execute("INSERT IGNORE INTO tipos_equipo (nombre) VALUES ('Consumible'),('Equipo de red'),('Computadora'),('Monitor'),('Herramienta'),('Mobiliario')")
    cur.execute('SELECT id,nombre FROM tipos_equipo')
    types = {r['nombre']:r['id'] for r in cur.fetchall()}
    cur.execute('SELECT id,nombre FROM estados')
    states = {r['nombre']:r['id'] for r in cur.fetchall()}
    groups = [('SW','Switch de 24 puertos','Equipo de red',10,'SW-24'),
              ('RT','Router','Equipo de red',5,'RT-100'),
              ('PC','Computadora portátil','Computadora',8,'PC-200'),
              ('MN','Monitor de 24 pulgadas','Monitor',12,'MON-24'),
              ('TL','Taladro eléctrico','Herramienta',6,'HER-5'),
              ('SL','Silla de oficina','Mobiliario',15,'MOB-1')]
    for prefix, name, category, count, model in groups:
        for i in range(1,count+1):
            code=f'DEMO3-{prefix}-{i:03d}'
            serial=f'SN-{code}'
            state = 'Asignado' if i == count and count > 5 else ('En mantenimiento' if i == count-1 and count > 5 else 'Disponible')
            location = 'Área técnica' if state == 'Asignado' else ('Taller de reparación' if state == 'En mantenimiento' else 'Almacén / Área D1')
            cur.execute('SELECT id FROM equipos WHERE codigo_inventario=%s OR serie=%s',(code,serial))
            if cur.fetchone():
                continue
            cur.execute('''INSERT INTO equipos (codigo_inventario,descripcion,tipo_id,marca,modelo,serie,estado_id,ubicacion,responsable)
                VALUES (%s,%s,%s,'Marca ficticia',%s,%s,%s,%s,%s)''',(code,name,types[category],model,serial,states[state],location,'Usuario de prueba' if state=='Asignado' else 'Sin asignar'))
            eid=cur.lastrowid
            cur.execute("INSERT INTO movimientos (equipo_id,accion,estado_nuevo,ubicacion_nueva,actor) VALUES (%s,'ALTA',%s,%s,'demo-v3')",(eid,state,location))
    for sku, name, qty, minimum in [('DEMO3-CB','Cable Ethernet',50,10),('DEMO3-CN','Conector RJ45',100,20)]:
        cur.execute('SELECT id FROM consumibles WHERE sku=%s',(sku,))
        if cur.fetchone():
            continue
        cur.execute('INSERT INTO consumibles (sku,descripcion,tipo_id,ubicacion,cantidad,minimo) VALUES (%s,%s,%s,%s,%s,%s)',(sku,name,types['Consumible'],'Almacén / Área D1',qty,minimum))
        sid=cur.lastrowid
        cur.execute("INSERT INTO movimientos_consumibles (consumible_id,accion,cantidad,saldo,motivo,actor) VALUES (%s,'ALTA',%s,%s,'Carga de demostración','demo-v3')",(sid,qty,qty))
    cur.execute('INSERT INTO demo_v3_cargado VALUES (1)')
