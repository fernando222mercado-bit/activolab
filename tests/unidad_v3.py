"""Pruebas del agrupamiento, identificadores y reparación UTF-8 sin Docker."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from inventory import repair_text, group_equipment, bulk_codes

for value in ('Almacén / Área D1','En reparación','Conexión eléctrica','Niño','¿Dónde?', 'Información – revisión'):
    assert repair_text(value)==value
    for encoding in ('latin1','cp1252'):
        try: bad=value.encode('utf-8').decode(encoding)
        except UnicodeDecodeError: continue
        assert repair_text(bad)==value,(bad,repair_text(bad))
        double=bad.encode('utf-8').decode('latin1')
        assert repair_text(double)==value,(double,repair_text(double))
assert repair_text('AlmacÃ©n / Área D1')=='Almacén / Área D1'
assert repair_text('AlmacÃ©n / Ãrea D1')=='Almacén / Área D1'
assert bulk_codes('SW','SN',3)==[('SW-001','SN-001'),('SW-002','SN-002'),('SW-003','SN-003')]
assert bulk_codes('SW','SN',1)==[('SW','SN')]
for n in (0,201):
    try: bulk_codes('SW','SN',n)
    except ValueError: pass
    else: raise AssertionError('Cantidad inválida aceptada')
a=dict(tipo_id=4,tipo='Red',descripcion='Switch',marca='Demo',modelo='A',estado='Disponible')
b=dict(a,estado='Baja')
c=dict(a,modelo='B')
g=group_equipment([a,b,c]);assert len(g)==2 and len(g[0]['units'])==2 and g[0]['disponibles']==1 and g[0]['bajas']==1
print('OK: pruebas unitarias de agrupación, códigos y texto UTF-8')
