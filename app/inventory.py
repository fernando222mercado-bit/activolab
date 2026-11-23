"""Agrupación de activos y reparación conservadora de texto español."""
import re
import hashlib
import json
from collections import OrderedDict


def article_key(row):
    identity = [str(row.get(k) or '').strip().casefold() for k in ('tipo_id','descripcion','marca','modelo')]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode('utf-8')).hexdigest()


def group_equipment(rows):
    groups = OrderedDict()
    for row in rows:
        key = article_key(row)
        group = groups.setdefault(key, dict(key=key, descripcion=row['descripcion'], tipo=row['tipo'],
                    marca=row['marca'], modelo=row['modelo'], units=[], disponibles=0, bajas=0))
        group['units'].append(row)
        group['disponibles'] += row['estado'] == 'Disponible'
        group['bajas'] += row['estado'] == 'Baja'
    return list(groups.values())


# Reemplaza únicamente secuencias dañadas conocidas; no recodifica el texto completo.
REPLACEMENTS = {}
for char in 'áéíóúüñÁÉÍÓÚÜÑ¿¡°ºª“”‘’–—…·':
    for encoding in ('latin1', 'cp1252'):
        try:
            bad = char.encode('utf-8').decode(encoding)
        except UnicodeDecodeError:
            continue
        REPLACEMENTS[bad] = char
        for second_encoding in ('latin1','cp1252'):
            try:
                REPLACEMENTS[bad.encode('utf-8').decode(second_encoding)] = char
            except UnicodeDecodeError:
                pass
REPLACEMENTS['Ãrea'] = 'Área'  # Variante con byte de control perdido en el ejemplo.
PATTERN = re.compile('|'.join(re.escape(k) for k in sorted(REPLACEMENTS, key=len, reverse=True)))


def repair_text(value):
    if not isinstance(value, str):
        return value
    # Algunas importaciones duplican la conversión; se limita a tres pasadas.
    for _ in range(3):
        updated = PATTERN.sub(lambda m: REPLACEMENTS[m.group()], value)
        # Repara doble codificación solo si toda la cadena es reversible y mejora.
        if updated == value and any(c in value for c in ('Ã','Â','â')):
            for encoding in ('cp1252','latin1'):
                try:
                    candidate = value.encode(encoding).decode('utf-8')
                except UnicodeError:
                    continue
                if sum(candidate.count(c) for c in ('Ã','Â','â')) < sum(value.count(c) for c in ('Ã','Â','â')):
                    updated = candidate
                    break
        if updated == value:
            break
        value = updated
    return value


def bulk_codes(code, serial, count):
    if not 1 <= count <= 200:
        raise ValueError('Cantidad inválida (1 a 200).')
    if count == 1:
        return [(code, serial)]
    if len(code) > 26 or len(serial) > 56:
        raise ValueError('Para alta masiva, el prefijo del código admite 26 caracteres y el de serie 56.')
    return [(f'{code}-{i:03d}', f'{serial}-{i:03d}') for i in range(1, count+1)]
