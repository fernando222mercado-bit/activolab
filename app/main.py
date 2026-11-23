"""Inventario generico de activos: CRUD, baja logica y auditoria."""
import hmac
import ipaddress
import os
import re
import secrets
from functools import wraps

import pymysql
from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template, request,
    session, url_for,
)
from pymysql.cursors import DictCursor
from inventory import group_equipment, bulk_codes
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', ''),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,  # Demo HTTP local; habilitar TLS para produccion.
    MAX_CONTENT_LENGTH=32768,
)

APP_NAME = os.getenv('APP_NAME', 'Inventario de Activos')
ORG_NAME = os.getenv('ORG_NAME', 'Organización de demostración')


def get_connection():
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'db'),
        port=int(os.getenv('DB_PORT', '3306')),
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        database=os.environ['DB_NAME'],
        cursorclass=DictCursor,
        connect_timeout=5,
        read_timeout=8,
        write_timeout=8,
        charset='utf8mb4',
        use_unicode=True,
        autocommit=False,
    )


ROLES = {'admin': 'Administrador', 'almacen': 'Jefe de almacén', 'usuario': 'Usuario normal'}


@app.before_request
def load_user():
    g.user = None
    g.settings = {'app_name': APP_NAME, 'org_name': ORG_NAME}
    if request.endpoint in ('health', 'static'):
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT app_name,org_name FROM configuracion WHERE id=1')
            g.settings = cur.fetchone() or g.settings
            if session.get('uid'):
                cur.execute('SELECT id,username,nombre,rol,activo,version_sesion FROM usuarios WHERE id=%s', (session['uid'],))
                user = cur.fetchone()
                if user and user['activo'] and user['version_sesion'] == session.get('version'):
                    g.user = user
                else:
                    session.clear()


def logged_in():
    return getattr(g, 'user', None) is not None


def roles_required(*roles):
    def decorate(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            if not logged_in():
                return redirect(url_for('login'))
            if roles and g.user['rol'] not in roles:
                abort(403)
            return handler(*args, **kwargs)
        return wrapped
    return decorate


login_required = roles_required()


@app.context_processor
def common_context():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_urlsafe(32)
    return dict(csrf_token=session['csrf_token'], sesion_activa=logged_in(),
                usuario=getattr(g, 'user', None), roles=ROLES,
                **getattr(g, 'settings', {'app_name': APP_NAME, 'org_name': ORG_NAME}))


@app.before_request
def protection():
    if request.method == 'POST':
        token = session.get('csrf_token', '')
        supplied = request.form.get('csrf_token', '')
        if not token or not hmac.compare_digest(token.encode("utf-8"), supplied.encode("utf-8")):
            abort(400, description='Formulario vencido o no válido. Recarga la página.')


@app.get('/health')
def health():
    """Endpoint para Docker: comprueba acceso real a MySQL."""
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) AS cantidad FROM equipos')
                total = cursor.fetchone()['cantidad']
                cursor.execute('SELECT id FROM configuracion WHERE id=1')
                if not cursor.fetchone():
                    raise ValueError('Configuración no inicializada')
                cursor.execute('SELECT COUNT(*) AS n FROM consumibles')
                cursor.fetchone()
                cursor.execute('SELECT id FROM usuarios LIMIT 1')
                if not cursor.fetchone():
                    raise ValueError('Sin administrador inicial')
        return jsonify(estado='ok', servicio='app', base_datos='conectada', registros=total), 200
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('Error en /health')
        return jsonify(estado='error', servicio='app', base_datos='no disponible'), 503


def audit_access(cur, user, username, event):
    # Nginx sobrescribe X-Real-IP; Flask no se publica al anfitrión.
    try:
        ip = str(ipaddress.ip_address(request.headers.get('X-Real-IP') or request.remote_addr or '0.0.0.0'))
    except ValueError:
        ip = '0.0.0.0'
    cur.execute('INSERT INTO accesos (usuario_id,username,evento,ip) VALUES (%s,%s,%s,%s)',
                (user['id'] if user else None, username[:80], event, ip))


@app.route('/login', methods=['GET','POST'])
def login():
    if logged_in():
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username','').strip()[:80]
        password = request.form.get('password','')
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM usuarios WHERE username=%s', (username,))
                user = cur.fetchone()
                ok = bool(user and user['activo'] and len(password)<=120 and check_password_hash(user['password_hash'],password))
                audit_access(cur, user, user['username'] if user else username, 'LOGIN_OK' if ok else 'LOGIN_FALLO')
                if ok:
                    cur.execute('UPDATE usuarios SET ultimo_acceso=CURRENT_TIMESTAMP WHERE id=%s',(user['id'],))
                conn.commit()
        if ok:
            session.clear()
            session.update(uid=user['id'], version=user['version_sesion'], csrf_token=secrets.token_urlsafe(32))
            return redirect(url_for('index'))
        flash('Usuario o contraseña incorrectos.', 'error')
    return render_template('login.html')


@app.post('/logout')
@login_required
def logout():
    with get_connection() as conn:
        with conn.cursor() as cur:
            audit_access(cur, g.user, g.user['username'], 'LOGOUT')
        conn.commit()
    session.clear()
    return redirect(url_for('login'))


def fetch_catalogs(cursor):
    cursor.execute('SELECT id, nombre FROM tipos_equipo ORDER BY nombre')
    tipos = cursor.fetchall()
    cursor.execute('SELECT id, nombre FROM estados ORDER BY id')
    estados = cursor.fetchall()
    return tipos, estados


def list_equipment(cursor, q, tipo, estado):
    query = '''
        SELECT e.id, e.tipo_id, e.codigo_inventario, e.descripcion, e.marca, e.modelo,
               e.serie, e.ubicacion, e.responsable, e.fecha_registro,
               t.nombre AS tipo, s.nombre AS estado
        FROM equipos AS e
        JOIN tipos_equipo AS t ON t.id = e.tipo_id
        JOIN estados AS s ON s.id = e.estado_id
        WHERE 1=1
    '''
    params = []
    if q:
        query += ''' AND (e.codigo_inventario LIKE %s OR e.descripcion LIKE %s
                     OR e.serie LIKE %s OR e.ubicacion LIKE %s)'''
        params.extend([f'%{q}%'] * 4)
    if tipo:
        query += ' AND e.tipo_id = %s'
        params.append(tipo)
    if estado:
        query += ' AND e.estado_id = %s'
        params.append(estado)
    query += ' ORDER BY e.descripcion, e.marca, e.modelo, e.id'
    cursor.execute(query, params)
    return cursor.fetchall()


@app.get('/')
@login_required
def index():
    q = request.args.get('q', '', type=str).strip()[:80]
    tipo = request.args.get('tipo', '', type=str)
    estado = request.args.get('estado', '', type=str)
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                tipos, estados = fetch_catalogs(cursor)
                equipos = list_equipment(cursor, q, tipo if tipo.isdecimal() else '',
                                          estado if estado.isdecimal() else '')
                cursor.execute('''SELECT COUNT(*) AS total,
                       SUM(CASE WHEN s.nombre = 'Disponible' THEN 1 ELSE 0 END) AS disponibles,
                       SUM(CASE WHEN s.nombre = 'Asignado' THEN 1 ELSE 0 END) AS asignados,
                       SUM(CASE WHEN s.nombre = 'Baja' THEN 1 ELSE 0 END) AS bajas
                       FROM equipos e JOIN estados s ON e.estado_id=s.id''')
                resumen = cursor.fetchone()
                groups = group_equipment(equipos)
                cursor.execute('SELECT clave,minimo FROM minimos_activos')
                minimums = {r['clave']:r['minimo'] for r in cursor.fetchall()}
                # Totales de existencias sin aplicar filtros de búsqueda o estado.
                all_groups = group_equipment(list_equipment(cursor, '', '', '')) if q or tipo or estado else groups
                totals = {r['key']:r for r in all_groups}
                for group in groups:
                    actual=totals[group['key']]
                    group['total']=len(actual['units'])-actual['bajas']
                    group['stock']=actual['disponibles']
                    group['minimo']=minimums.get(group['key'],0)
                cursor.execute('SELECT COALESCE(SUM(cantidad),0) AS total, COUNT(*) AS articulos FROM consumibles')
                stock_summary=cursor.fetchone()
                sql='SELECT c.*, t.nombre AS tipo FROM consumibles c JOIN tipos_equipo t ON t.id=c.tipo_id WHERE 1=1'
                args=[]
                if q:
                    sql += ' AND (c.sku LIKE %s OR c.descripcion LIKE %s OR c.ubicacion LIKE %s)'
                    args.extend([f'%{q}%']*3)
                if tipo.isdecimal():
                    sql += ' AND c.tipo_id=%s'
                    args.append(tipo)
                if estado.isdecimal():
                    # Los consumibles solo tienen existencias disponibles, no estados por unidad.
                    sql += " AND EXISTS (SELECT 1 FROM estados WHERE id=%s AND nombre='Disponible') AND c.cantidad>0"
                    args.append(estado)
                cursor.execute(sql+' ORDER BY c.descripcion',args)
                consumibles=cursor.fetchall()
        return render_template('index.html', equipos=equipos, grupos=groups, consumibles=consumibles, stock_summary=stock_summary,
                               articulos_total=len(all_groups)+stock_summary['articulos'], tipos=tipos,
                               estados=estados, resumen=resumen, q=q,
                               filtro_tipo=tipo, filtro_estado=estado)
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('No se pudo cargar el inventario')
        return render_template('error.html'), 503


def read_form(form):
    """Normaliza y valida los valores sin confiar en el navegador."""
    values = {
        'codigo_inventario': form.get('codigo_inventario', '').strip().upper(),
        'descripcion': form.get('descripcion', '').strip(),
        'tipo_id': form.get('tipo_id', '').strip(),
        'marca': form.get('marca', '').strip(),
        'modelo': form.get('modelo', '').strip(),
        'serie': form.get('serie', '').strip().upper(),
        'estado_id': form.get('estado_id', '').strip(),
        'ubicacion': form.get('ubicacion', '').strip(),
        'responsable': form.get('responsable', '').strip() or 'Sin asignar',
    }
    errors = []
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,29}', values['codigo_inventario']):
        errors.append('El código debe tener de 1 a 30 caracteres: letras, números, puntos, guiones o guiones bajos; comienza con letra o número.')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,59}', values['serie']):
        errors.append('La serie debe tener de 1 a 60 caracteres: letras, números, puntos, guiones o guiones bajos; comienza con letra o número.')
    lengths = {
        'descripcion': 180, 'marca': 80, 'modelo': 80,
        'ubicacion': 120, 'responsable': 120,
    }
    for key, limit in lengths.items():
        if len(values[key]) > limit:
            errors.append(f'El campo {key} supera {limit} caracteres.')
    if not values['descripcion'] or not values['ubicacion']:
        errors.append('La descripción y la ubicación son obligatorias.')
    for key in ('tipo_id', 'estado_id'):
        if not values[key].isdecimal() or int(values[key]) < 1:
            errors.append(f'Debes seleccionar un {"tipo" if key == "tipo_id" else "estado"} válido.')
    return values, errors


def render_form(cursor, *, equipment=None, values=None, errors=None):
    tipos, estados = fetch_catalogs(cursor)
    return render_template('form.html', equipo=equipment, values=values or equipment or {},
                           tipos=tipos, estados=estados, errors=errors or [])


def catalog_values_valid(cursor, values):
    cursor.execute('SELECT id FROM tipos_equipo WHERE id=%s', (values['tipo_id'],))
    tipo_ok = cursor.fetchone() is not None
    cursor.execute('SELECT id FROM estados WHERE id=%s', (values['estado_id'],))
    estado_ok = cursor.fetchone() is not None
    return tipo_ok and estado_ok


@app.route('/equipos/nuevo', methods=['GET', 'POST'])
@roles_required('admin')
def new_equipment():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                if request.method == 'GET':
                    key=request.args.get('grupo','')
                    if key:
                        groups=group_equipment(list_equipment(cursor,'','',''))
                        source=next((group['units'][0] for group in groups if group['key']==key),None)
                        if source is None: abort(404)
                        values={k:source[k] for k in ('descripcion','tipo_id','marca','modelo','ubicacion')}
                        return render_form(cursor,values=values)
                    return render_form(cursor)
                values, errors = read_form(request.form)
                values['cantidad'] = request.form.get('cantidad','1')
                try:
                    pairs = bulk_codes(values['codigo_inventario'], values['serie'], int(values['cantidad']))
                except ValueError:
                    errors.append('Usa una cantidad de 1 a 200 y prefijos de máximo 26 y 56 caracteres para altas múltiples.')
                if not errors and not catalog_values_valid(cursor, values):
                    errors.append('El tipo o estado seleccionado no existe.')
                if errors:
                    return render_form(cursor, values=values, errors=errors), 400
                try:
                    cursor.execute('SELECT nombre FROM estados WHERE id=%s', (values['estado_id'],))
                    estado = cursor.fetchone()['nombre']
                    for code, serial in pairs:
                        cursor.execute('''INSERT INTO equipos
                            (codigo_inventario, descripcion, tipo_id, marca, modelo, serie,
                             estado_id, ubicacion, responsable)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (code, values['descripcion'], values['tipo_id'], values['marca'], values['modelo'], serial, values['estado_id'], values['ubicacion'], values['responsable']))
                        equipo_id = cursor.lastrowid
                        cursor.execute('''INSERT INTO movimientos
                            (equipo_id, accion, estado_nuevo, ubicacion_nueva, actor)
                            VALUES (%s, 'ALTA', %s, %s, %s)''',
                            (equipo_id, estado, values['ubicacion'], g.user['username']))
                    connection.commit()
                except pymysql.IntegrityError as exc:
                    connection.rollback()
                    if exc.args and exc.args[0] == 1062:
                        return render_form(cursor, values=values, errors=[
                            'El código o el número de serie ya existe. Usa uno diferente.'
                        ]), 409
                    raise
        flash(f'{len(pairs)} unidad(es) registradas correctamente.', 'success')
        return redirect(url_for('index'))
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('Error al registrar equipo')
        return render_template('error.html'), 503


def find_equipment(cursor, equipo_id, lock=False):
    query = '''SELECT e.*, s.nombre AS estado_nombre FROM equipos AS e
               JOIN estados AS s ON s.id=e.estado_id WHERE e.id=%s'''
    if lock:
        query += ' FOR UPDATE'
    cursor.execute(query, (equipo_id,))
    return cursor.fetchone()


@app.route('/equipos/<int:equipo_id>/editar', methods=['GET', 'POST'])
@roles_required('admin','almacen')
def edit_equipment(equipo_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                old = find_equipment(cursor, equipo_id, lock=(request.method == 'POST'))
                if old is None:
                    abort(404)
                if g.user['rol'] == 'almacen' and old['estado_nombre'] == 'Baja':
                    abort(403)
                if request.method == 'GET':
                    return render_form(cursor, equipment=old)
                form = request.form.to_dict()
                if g.user['rol'] == 'almacen':
                    for key in ('codigo_inventario','descripcion','tipo_id','marca','modelo','serie'):
                        form[key] = str(old[key] or '')
                    cursor.execute('SELECT nombre FROM estados WHERE id=%s', (form.get('estado_id',''),))
                    target = cursor.fetchone()
                    if target and target['nombre'] == 'Baja':
                        abort(403)
                values, errors = read_form(form)
                if not errors and not catalog_values_valid(cursor, values):
                    errors.append('El tipo o estado seleccionado no existe.')
                if errors:
                    return render_form(cursor, equipment=old, values=values, errors=errors), 400
                try:
                    cursor.execute('''UPDATE equipos SET codigo_inventario=%s, descripcion=%s,
                        tipo_id=%s, marca=%s, modelo=%s, serie=%s, estado_id=%s,
                        ubicacion=%s, responsable=%s WHERE id=%s''', tuple(values[k] for k in (
                            'codigo_inventario','descripcion','tipo_id','marca','modelo','serie',
                            'estado_id','ubicacion','responsable')) + (equipo_id,))
                    changed = any(str(old[k] or '') != str(values[k] or '') for k in values)
                    if changed:
                        cursor.execute('SELECT nombre FROM estados WHERE id=%s', (values['estado_id'],))
                        new_status = cursor.fetchone()['nombre']
                        cursor.execute('''INSERT INTO movimientos
                            (equipo_id, accion, estado_anterior, estado_nuevo,
                             ubicacion_anterior, ubicacion_nueva, actor)
                            VALUES (%s,'ACTUALIZACION',%s,%s,%s,%s,%s)''',
                            (equipo_id, old['estado_nombre'], new_status,
                             old['ubicacion'], values['ubicacion'], g.user['username']))
                    connection.commit()
                except pymysql.IntegrityError as exc:
                    connection.rollback()
                    if exc.args and exc.args[0] == 1062:
                        return render_form(cursor, equipment=old, values=values, errors=[
                            'Otro equipo ya tiene ese código o número de serie.'
                        ]), 409
                    raise
        flash('Cambios guardados y movimiento registrado.', 'success')
        return redirect(url_for('index'))
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('Error al actualizar equipo')
        return render_template('error.html'), 503


@app.post('/equipos/<int:equipo_id>/baja')
@roles_required('admin')
def decommission_equipment(equipo_id):
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                old = find_equipment(cursor, equipo_id, lock=True)
                if old is None:
                    abort(404)
                if old['estado_nombre'] == 'Baja':
                    flash('El equipo ya estaba dado de baja.', 'info')
                else:
                    cursor.execute("SELECT id FROM estados WHERE nombre='Baja'")
                    baja = cursor.fetchone()
                    if not baja:
                        raise ValueError('No existe el estado Baja')
                    cursor.execute('UPDATE equipos SET estado_id=%s WHERE id=%s',
                                   (baja['id'], equipo_id))
                    cursor.execute('''INSERT INTO movimientos
                        (equipo_id, accion, estado_anterior, estado_nuevo,
                         ubicacion_anterior, ubicacion_nueva, actor)
                        VALUES (%s,'BAJA',%s,'Baja',%s,%s,%s)''',
                        (equipo_id, old['estado_nombre'], old['ubicacion'], old['ubicacion'], g.user['username']))
                    connection.commit()
                    flash('Equipo dado de baja sin eliminar su historial.', 'success')
        return redirect(url_for('index'))
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('Error al dar de baja equipo')
        return render_template('error.html'), 503


@app.route('/categorias', methods=['GET', 'POST'])
@roles_required('admin')
def categories():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                if request.method == 'POST':
                    nombre = request.form.get('nombre', '').strip()
                    if not nombre or len(nombre) > 90:
                        flash('Indica una categoría de 1 a 90 caracteres.', 'error')
                    else:
                        try:
                            cursor.execute('INSERT INTO tipos_equipo (nombre) VALUES (%s)', (nombre,))
                            connection.commit()
                            flash('Categoría registrada.', 'success')
                        except pymysql.IntegrityError as exc:
                            connection.rollback()
                            if exc.args and exc.args[0] == 1062:
                                flash('Esa categoría ya existe.', 'error')
                            else:
                                raise
                    return redirect(url_for('categories'))
                tipos, _ = fetch_catalogs(cursor)
        return render_template('categories.html', tipos=tipos)
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('Error al administrar categorías')
        return render_template('error.html'), 503


@app.get('/movimientos')
@roles_required('admin','almacen')
def movements():
    try:
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT m.*, e.codigo_inventario, e.descripcion
                    FROM movimientos m JOIN equipos e ON e.id=m.equipo_id
                    ORDER BY m.id DESC LIMIT 200''')
                rows = cursor.fetchall()
                cursor.execute('''SELECT m.*,c.sku,c.descripcion FROM movimientos_consumibles m
                    JOIN consumibles c ON c.id=m.consumible_id ORDER BY m.id DESC LIMIT 200''')
                stock_moves=cursor.fetchall()
        return render_template('history.html', movimientos=rows, stock_moves=stock_moves)
    except (pymysql.MySQLError, OSError, KeyError, ValueError):
        app.logger.exception('Error al consultar movimientos')
        return render_template('error.html'), 503


@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message='No se encontró ese equipo o página.'), 404


@app.errorhandler(400)
def bad_request(error):
    return render_template('error.html', message=str(error.description)), 400


@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html', message='Tu perfil no tiene permiso para realizar esta operación.'), 403


@app.errorhandler(pymysql.MySQLError)
def db_error(error):
    app.logger.exception('Error de base de datos')
    return render_template('error.html'), 503


@app.route('/usuarios', methods=['GET','POST'])
@roles_required('admin')
def users():
    with get_connection() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                username = request.form.get('username','').strip()
                nombre = request.form.get('nombre','').strip()
                password = request.form.get('password','')
                rol = request.form.get('rol','')
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{2,79}', username) or not 1<=len(nombre)<=120 or rol not in ROLES or not 10<=len(password)<=120:
                    flash('Usuario de 3–80 caracteres, nombre, rol y contraseña de 10–120 caracteres obligatorios.', 'error')
                else:
                    try:
                        cur.execute('INSERT INTO usuarios (username,nombre,password_hash,rol) VALUES (%s,%s,%s,%s)', (username,nombre,generate_password_hash(password),rol))
                        conn.commit()
                        flash('Cuenta creada.', 'success')
                    except pymysql.IntegrityError as exc:
                        if exc.args[0] != 1062: raise
                        conn.rollback()
                        flash('El usuario ya existe.', 'error')
                return redirect(url_for('users'))
            cur.execute('SELECT id,username,nombre,rol,activo,creado,ultimo_acceso FROM usuarios ORDER BY id')
            rows = cur.fetchall()
    return render_template('users.html', cuentas=rows)


@app.route('/usuarios/<int:uid>/editar', methods=['GET','POST'])
@roles_required('admin')
def edit_user(uid):
    with get_connection() as conn:
        with conn.cursor() as cur:
            if request.method == 'POST':
                # Serializa mutaciones de cuentas y vuelve a validar al administrador.
                cur.execute('SELECT id FROM configuracion WHERE id=1 FOR UPDATE')
                cur.fetchone()
                cur.execute('SELECT rol,activo,version_sesion FROM usuarios WHERE id=%s FOR UPDATE', (g.user['id'],))
                current = cur.fetchone()
                if not current or not current['activo'] or current['rol'] != 'admin' or current['version_sesion'] != session.get('version'):
                    abort(403)
            cur.execute('SELECT id,username,nombre,rol,activo FROM usuarios WHERE id=%s' + (' FOR UPDATE' if request.method=='POST' else ''), (uid,))
            account = cur.fetchone()
            if not account: abort(404)
            if request.method == 'POST':
                nombre = request.form.get('nombre','').strip()
                rol = request.form.get('rol','')
                activo = request.form.get('activo') == '1'
                password = request.form.get('password','')
                if uid == g.user['id'] and (rol != 'admin' or not activo):
                    abort(403)
                if not 1<=len(nombre)<=120 or rol not in ROLES or (password and not 10<=len(password)<=120):
                    flash('Revisa los campos. La contraseña nueva debe tener 10–120 caracteres.', 'error')
                    return render_template('user_edit.html', cuenta=account), 400
                invalidate = int(rol != account['rol'] or activo != bool(account['activo']) or bool(password))
                cur.execute('UPDATE usuarios SET nombre=%s,rol=%s,activo=%s,version_sesion=version_sesion+%s WHERE id=%s', (nombre,rol,activo,invalidate,uid))
                if password:
                    cur.execute('UPDATE usuarios SET password_hash=%s WHERE id=%s',(generate_password_hash(password),uid))
                conn.commit()
                if uid == g.user['id'] and invalidate: session.clear()
                flash('Cuenta actualizada. Las sesiones anteriores se invalidan si cambias acceso o contraseña.', 'success')
                return redirect(url_for('users'))
    return render_template('user_edit.html', cuenta=account)


@app.get('/accesos')
@roles_required('admin')
def access_log():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT username,evento,ip,fecha FROM accesos ORDER BY id DESC LIMIT 200')
            rows = cur.fetchall()
    return render_template('access.html', accesos=rows)


@app.route('/configuracion', methods=['GET','POST'])
@roles_required('admin')
def settings():
    if request.method == 'POST':
        title = request.form.get('app_name','').strip()
        org = request.form.get('org_name','').strip()
        if not 1<=len(title)<=120 or not 1<=len(org)<=120:
            flash('Ambos nombres son obligatorios (máximo 120 caracteres).','error')
            return render_template('settings.html'), 400
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE configuracion SET app_name=%s,org_name=%s WHERE id=1',(title,org))
            conn.commit()
        flash('Configuración guardada.','success')
        return redirect(url_for('settings'))
    return render_template('settings.html')


@app.route('/mi-cuenta', methods=['GET','POST'])
@login_required
def profile():
    if request.method == 'POST':
        current = request.form.get('current_password','')
        new = request.form.get('password','')
        if len(current)>120 or not 10<=len(new)<=120 or new != request.form.get('confirm_password',''):
            flash('Verifica la contraseña nueva (10–120 caracteres) y su confirmación.', 'error')
            return render_template('profile.html'), 400
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT password_hash,activo,version_sesion FROM usuarios WHERE id=%s FOR UPDATE',(g.user['id'],))
                account = cur.fetchone()
                if not account or not account['activo'] or account['version_sesion'] != session.get('version') or not check_password_hash(account['password_hash'],current):
                    flash('No se pudo verificar la contraseña actual.', 'error')
                    return render_template('profile.html'), 400
                cur.execute('UPDATE usuarios SET password_hash=%s,version_sesion=version_sesion+1 WHERE id=%s',(generate_password_hash(new),g.user['id']))
            conn.commit()
        session.clear()
        flash('Contraseña cambiada. Inicia sesión nuevamente.', 'success')
        return redirect(url_for('login'))
    return render_template('profile.html')


@app.post('/articulos/<clave>/minimo')
@roles_required('admin')
def set_minimum(clave):
    if not re.fullmatch(r'[0-9a-f]{64}', clave):
        abort(404)
    minimo = request.form.get('minimo', type=int)
    if minimo is None or not 0 <= minimo <= 1000000:
        abort(400, description='Mínimo inválido.')
    with get_connection() as conn:
        with conn.cursor() as cur:
            if clave not in {r['key'] for r in group_equipment(list_equipment(cur,'','',''))}:
                abort(404)
            cur.execute('INSERT INTO minimos_activos (clave,minimo) VALUES (%s,%s) ON DUPLICATE KEY UPDATE minimo=%s',(clave,minimo,minimo))
        conn.commit()
    flash('Existencia mínima guardada.', 'success')
    return redirect(url_for('index'))


@app.route('/consumibles/nuevo', methods=['GET','POST'])
@roles_required('admin')
def new_stock():
    with get_connection() as conn:
        with conn.cursor() as cur:
            tipos,_=fetch_catalogs(cur)
            if request.method == 'POST':
                sku=request.form.get('sku','').strip().upper()
                name=request.form.get('descripcion','').strip()
                location=request.form.get('ubicacion','').strip()
                tipo=request.form.get('tipo_id',type=int)
                qty=request.form.get('cantidad',type=int)
                minimum=request.form.get('minimo',type=int)
                if not re.fullmatch(r'[A-Z0-9][A-Z0-9._-]{0,29}',sku) or not 1<=len(name)<=180 or not 1<=len(location)<=120 or tipo not in {r['id'] for r in tipos} or qty is None or minimum is None or not 0<=qty<=1000000 or not 0<=minimum<=1000000:
                    abort(400,description='Revisa código, descripción, categoría, ubicación, cantidad y mínimo.')
                try:
                    cur.execute('INSERT INTO consumibles (sku,descripcion,tipo_id,ubicacion,cantidad,minimo) VALUES (%s,%s,%s,%s,%s,%s)',(sku,name,tipo,location,qty,minimum))
                    cid=cur.lastrowid
                    cur.execute("INSERT INTO movimientos_consumibles (consumible_id,accion,cantidad,saldo,motivo,actor) VALUES (%s,'ALTA',%s,%s,'Existencia inicial',%s)",(cid,qty,qty,g.user['username']))
                    conn.commit()
                except pymysql.IntegrityError as exc:
                    conn.rollback()
                    if exc.args[0] != 1062: raise
                    flash('El SKU del consumible ya existe.', 'error')
                    return render_template('stock_form.html',tipos=tipos),409
                flash('Consumible registrado.', 'success')
                return redirect(url_for('index'))
    return render_template('stock_form.html',tipos=tipos)


@app.route('/consumibles/<int:cid>/movimiento', methods=['GET','POST'])
@roles_required('admin','almacen')
def stock_move(cid):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM consumibles WHERE id=%s'+(' FOR UPDATE' if request.method=='POST' else ''),(cid,))
            item=cur.fetchone()
            if not item: abort(404)
            if request.method=='POST':
                action=request.form.get('accion')
                qty=request.form.get('cantidad',type=int)
                reason=request.form.get('motivo','').strip()
                if action not in ('ENTRADA','SALIDA') or qty is None or not 1<=qty<=1000000 or not 1<=len(reason)<=180:
                    abort(400,description='Indica una cantidad positiva y un motivo válido.')
                balance=item['cantidad']+(qty if action=='ENTRADA' else -qty)
                if not 0<=balance<=1000000:
                    flash('Movimiento rechazado: existencia insuficiente o límite de stock excedido.','error')
                    return render_template('stock_move.html',item=item),400
                cur.execute('UPDATE consumibles SET cantidad=%s WHERE id=%s',(balance,cid))
                cur.execute('INSERT INTO movimientos_consumibles (consumible_id,accion,cantidad,saldo,motivo,actor) VALUES (%s,%s,%s,%s,%s,%s)',(cid,action,qty,balance,reason,g.user['username']))
                conn.commit()
                flash('Movimiento registrado.', 'success')
                return redirect(url_for('index'))
    return render_template('stock_move.html',item=item)


@app.post('/consumibles/<int:cid>/minimo')
@roles_required('admin')
def stock_minimum(cid):
    value=request.form.get('minimo',type=int)
    if value is None or not 0<=value<=1000000: abort(400,description='Mínimo inválido.')
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id FROM consumibles WHERE id=%s FOR UPDATE',(cid,))
            if not cur.fetchone(): abort(404)
            cur.execute('UPDATE consumibles SET minimo=%s WHERE id=%s',(value,cid))
        conn.commit()
    flash('Existencia mínima guardada.','success')
    return redirect(url_for('index'))
