"""Pruebas contra una instalación de CI DESECHABLE, no contra inventario activo."""
import http.cookiejar
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = os.getenv('BASE_URL', 'http://127.0.0.1:8080').rstrip('/')
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def request(path, data=None, expected=200):
    raw = urllib.parse.urlencode(data).encode() if data is not None else None
    try:
        response = client.open(BASE + path, data=raw, timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        assert response.code == expected, (path, response.code, expected)
        return response.read().decode('utf-8')


def token(page):
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


health = json.loads(request('/health'))
assert health['estado'] == 'ok' and health['base_datos'] == 'conectada'
assert health['registros'] == 62, 'La prueba exige una base nueva con 62 registros'
print('OK: Nginx, Flask, MySQL y carga inicial')
page = request('/login')
page = request('/login', {'csrf_token': token(page), 'username': os.environ['TEST_USERNAME'], 'password': os.environ['TEST_PASSWORD']})
assert 'INV-001' in page
print('OK: inicio de sesión')
categorias = request('/categorias')
assert 'Computadora' in categorias
categorias = request('/categorias', {'csrf_token': token(categorias), 'nombre': 'Categoría CI'})
assert 'Categoría CI' in categorias
print('OK: creación de categorías')
form = request('/equipos/nuevo')
assert 'Categoría CI' in form
data = dict(csrf_token=token(form), codigo_inventario='ACTIVO-CI01', serie='SERIE-CI01', descripcion='Monitor CI', tipo_id='2', estado_id='1', marca='Demo', modelo='CI', ubicacion='Estante CI', responsable='Prueba CI')
request('/equipos/nuevo', data)
page = request('/?q=ACTIVO-CI01')
assert 'Monitor CI' in page
edit = re.search(r'href="(/equipos/\d+/editar)"', page).group(1)
print('OK: alta y búsqueda')
request('/equipos/nuevo', data, 409)
print('OK: rechazo de duplicados')
data.update(csrf_token=token(request(edit)), estado_id='2', ubicacion='Sala CI')
request(edit, data)
page = request('/?q=ACTIVO-CI01')
assert 'Sala CI' in page and 'Asignado' in page
request(edit.replace('/editar','/baja'), {'csrf_token': token(page)})
page = request('/?q=ACTIVO-CI01')
assert 'Monitor CI' in page and 'Baja' in page
history = request('/movimientos')
assert all(x in history for x in ('ACTIVO-CI01','ALTA','ACTUALIZACION','BAJA'))
assert json.loads(request('/health'))['registros'] == 63
print('OK: edición, baja lógica e historial')

# RBAC: tres sesiones independientes y comprobación de restricciones en servidor.
def new_client():
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

admin = client
page = request('/usuarios')
for username, role, name in [('jefe-ci','almacen','Jefe CI'),('lector-ci','usuario','Lector CI')]:
    page = request('/usuarios', dict(csrf_token=token(page), username=username, nombre=name, rol=role, password='ci_password_123'))
    assert username in page
lector_edit = re.search(r'<td>lector-ci</td>.*?href="(/usuarios/\d+/editar)"', page).group(1)
page = request('/configuracion')
request('/configuracion', dict(csrf_token=token(page), app_name='Inventario CI', org_name='Organización CI'))
assert 'Organización CI' in request('/')

client = new_client()
login_page = request('/login')
request('/login', dict(csrf_token=token(login_page), username='lector-ci', password='incorrecta'))
page = request('/login')
page = request('/login', dict(csrf_token=token(page), username='lector-ci', password='ci_password_123'))
assert 'Usuario normal' in page and 'INV-001' in page
for path in ('/usuarios','/accesos','/configuracion','/equipos/nuevo','/categorias','/movimientos',edit):
    request(path, expected=403)
request('/equipos/nuevo', dict(data, csrf_token=token(page)), expected=403)
request(edit.replace('/editar','/baja'), dict(csrf_token=token(page)), expected=403)
lector = client
print('OK: usuario normal solo consulta y recibe HTTP 403 en rutas protegidas')

client = new_client()
page = request('/login')
page = request('/login', dict(csrf_token=token(page), username='jefe-ci', password='ci_password_123'))
assert 'Jefe de almacén' in page
for path in ('/usuarios','/accesos','/configuracion','/equipos/nuevo','/categorias',edit):
    request(path, expected=403)  # edit es el activo dado de baja anteriormente
page = request('/?q=INV-001')
manager_edit = re.search(r'href="(/equipos/\d+/editar)"',page).group(1)
form = request(manager_edit)
assert 'name="codigo_inventario"' not in form
request(manager_edit, dict(csrf_token=token(form), estado_id='6', ubicacion='Sala jefe', responsable='Jefe CI'), expected=403)
request(manager_edit, dict(csrf_token=token(form), estado_id='2', ubicacion='Sala jefe', responsable='Jefe CI', codigo_inventario='ALTERADO', descripcion='Alterado'))
page = request('/?q=INV-001')
assert 'Sala jefe' in page and 'Computadora de escritorio' in page and 'ALTERADO' not in page
assert 'jefe-ci' in request('/movimientos')
request(manager_edit.replace('/editar','/baja'), dict(csrf_token=token(page)), expected=403)
request('/logout', dict(csrf_token=token(page)))
print('OK: jefe de almacén modifica solo campos operativos y queda registrado como actor')

client = admin
page = request('/accesos')
assert all(x in page for x in ('LOGIN_OK','LOGIN_FALLO','LOGOUT','jefe-ci','lector-ci'))
page = request(lector_edit)
request(lector_edit, dict(csrf_token=token(page), nombre='Lector CI', rol='usuario', activo='0', password=''))
client = lector
assert 'Iniciar sesión' in request('/')
print('OK: auditoría, configuración y revocación de sesiones al desactivar cuenta')

# Inventario híbrido, agrupación, altas masivas, UTF-8 y stock.
client = admin
page = request('/?q=DEMO3-SW')
assert '10</b> unidades' in page and all(f'DEMO3-SW-{i:03d}' in page for i in range(1,11))
assert 'Almacén / Área D1' in page and 'AlmacÃ' not in page
form=request('/equipos/nuevo')
bulk=dict(data, csrf_token=token(form), codigo_inventario='LOTE-CI', serie='SERIE-LOTE-CI', descripcion='Cámara CI', cantidad='3', estado_id='1', ubicacion='Almacén / Área D1')
request('/equipos/nuevo',bulk)
page=request('/?q=LOTE-CI')
assert '3</b> unidades' in page and all(f'LOTE-CI-{i:03d}' in page for i in range(1,4))
request('/equipos/nuevo',bulk,409)
assert json.loads(request('/health'))['registros']==66
minimum = re.search(r'action="(/articulos/[a-f0-9]+/minimo)"',page).group(1)
request(minimum,dict(csrf_token=token(page),minimo='4'))
assert 'Stock bajo' in request('/?q=LOTE-CI')
page=request('/?q=DEMO3-CB')
path=re.search(r'href="(/consumibles/\d+/movimiento)"',page).group(1)
form=request(path)
request(path,dict(csrf_token=token(form),accion='SALIDA',cantidad='5',motivo='Préstamo CI'))
assert '>45</span>' in request('/?q=DEMO3-CB')
form=request(path)
request(path,dict(csrf_token=token(form),accion='SALIDA',cantidad='46',motivo='Rechazar CI'),400)
assert '>45</span>' in request('/?q=DEMO3-CB')
form=request(path)
request(path,dict(csrf_token=token(form),accion='ENTRADA',cantidad='5',motivo='Devolución CI'))
assert '>50</span>' in request('/?q=DEMO3-CB')
assert 'Préstamo CI' in request('/movimientos')
client=new_client()
page=request('/login')
page=request('/login',dict(csrf_token=token(page),username='jefe-ci',password='ci_password_123'))
request('/consumibles/nuevo',expected=403)
form=request(path)
request(path,dict(csrf_token=token(form),accion='ENTRADA',cantidad='1',motivo='Entrada jefe CI'))
assert '>51</span>' in request('/?q=DEMO3-CB')
client=new_client()
page=request('/login')
# El lector anterior fue desactivado; crea otra cuenta de consulta para esta prueba.
client=admin
page=request('/usuarios')
request('/usuarios',dict(csrf_token=token(page),username='lector-v3',nombre='Lector V3',rol='usuario',password='ci_password_123'))
client=new_client()
page=request('/login')
page=request('/login',dict(csrf_token=token(page),username='lector-v3',password='ci_password_123'))
assert 'DEMO3-CB' in page
request(path,expected=403)
request(path,dict(csrf_token=token(page),accion='ENTRADA',cantidad='1',motivo='No autorizado'),403)
print('OK: inventario híbrido, alta masiva, UTF-8, mínimos y permisos de stock')
