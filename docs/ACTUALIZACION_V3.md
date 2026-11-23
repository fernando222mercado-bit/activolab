# ActivoLab v3.0 | Guía de actualización

## Instalación existente (v2)

1. Copia `ActivoLab_v3_Actualizacion.zip` al directorio personal de tu usuario en Ubuntu (por ejemplo mediante SCP).
2. Entra en la **carpeta del proyecto que ya está desplegado**. No cambies de carpeta de despliegue ni de nombre de Compose. Guarda copia de tus fuentes, `compose.yaml`, configuración de Nginx y `.env` fuera del repositorio, protegida. Comprueba `sudo docker compose ps` y `sudo docker compose ls`. Debe aparecer la base activa.
3. Crea un respaldo antes de sustituir archivos:

```bash
sudo bash scripts/respaldo.sh
```

4. Si tu `.env` tiene `APP_IMAGE=...`, coméntala temporalmente con `sudo nano .env` para compilar la versión local. No cambies las claves ni `COMPOSE_PROJECT_NAME`. Si hiciste modificaciones propias a Compose, compáralas con el archivo nuevo y conserva ajustes de puertos, volumen y red.
5. En la misma carpeta activa:

```bash
unzip -o ~/ActivoLab_v3_Actualizacion.zip
sudo bash scripts/actualizar_v3.sh
```

El parche incluye las rutas relativas del proyecto, no `.env`, `.git`, respaldos o datos. El script verifica la base activa, detiene Nginx y Flask, genera otro respaldo, construye la aplicación, aplica una migración aditiva, repara secuencias reconocibles de texto y carga ejemplos una sola vez. Finalmente inicia Nginx. Usa `--sin-demo` si no quieres insertar ejemplos en una base existente. Si falla, consulta `sudo docker compose logs --tail=100 app db nginx` y conserva los respaldos. No uses `down -v` ni borres el volumen.

## Desde cero

```bash
unzip ActivoLab_v3_Proyecto_Final.zip
cd ActivoLab_v3_Proyecto_Final
sudo bash scripts/instalar_requisitos_inventario.sh --deploy .
```

El archivo `.env` se genera en el despliegue; consulta las credenciales iniciales con `sudo nano .env`. Usa contraseñas de laboratorio diferentes y no publiques el archivo. La carga inicial conserva los seis ejemplos originales y añade 56 activos ficticios con prefijo DEMO3 y dos consumibles (150 unidades). Una base existente no recibe otra vez los seis del init.sql. No se crean cuentas de demostración adicionales.

## Cómo demostrar

- Busca `DEMO3-SW` y abre el grupo de switches: diez unidades, ocho disponibles, una asignada y una en mantenimiento. Cada una conserva serie, ubicación, responsable y estado. Elige **Agregar unidades** para reutilizar descripción, categoría, marca y modelo; indica cantidad y prefijos únicos. Para múltiples unidades el sistema agrega sufijos -001, -002, etc. Las series generadas son identificadores internos; registra las reales editando cada unidad.
- Los grupos de activos se forman por descripción, categoría, marca y modelo (ignorando mayúsculas y espacios exteriores). No requieren un SKU común nuevo ni cambian los códigos existentes. Cambiar esos datos en una unidad puede moverla a otro grupo; los mínimos se almacenan por identidad del grupo y deben configurarse de nuevo si cambia esa identidad. Los totales de grupo excluyen las bajas, pero las unidades dadas de baja siguen visibles para trazabilidad. Los filtros muestran las unidades coincidentes sin alterar el total del grupo.
- En **Artículos por cantidad**, busca `DEMO3-CB` (50 cables) o `DEMO3-CN` (100 conectores). Registra una salida de 5, comprueba el saldo y abre Historial. Prueba una salida superior al saldo: debe rechazarse sin modificar la existencia. Cada consumible posee un SKU único y una ubicación. No hay transferencias entre múltiples almacenes, ventas o lotes en este prototipo.
- Como administrador puedes dar altas individuales/masivas y de consumibles, ajustar mínimos, administrar cuentas, categorías y configuración. El jefe de almacén puede editar campos operativos de activos y registrar entradas/salidas de consumibles; el usuario normal solo consulta. Las restricciones se verifican en el servidor.

## Codificación

HTML, Flask, PyMySQL, Nginx e importaciones SQL trabajan con UTF-8/utf8mb4. La reparación es conservadora: convierte secuencias típicas como `AlmacÃ©n` en `Almacén`, incluyendo variantes dobles conocidas, sin recodificar textos correctos de manera indiscriminada. Conserva los códigos, series, identificadores de usuario, contraseñas y claves. Si una categoría o estado reparado colisiona con otro existente, omite la fila y avisa por consola. No puede recuperar caracteres que ya fueron sustituidos por `?` o `�`; esos deben corregirse con el valor original. Si aparecen nuevos casos, revisa los registros originales y la fuente de importación.

Para revisar y aplicar manualmente (con copia de seguridad previa, y sin usuarios escribiendo):

```bash
sudo docker compose exec -T app python schema.py --repair-preview
sudo docker compose exec -T app python schema.py --repair-apply
sudo docker compose exec -T app python schema.py --demo
```

La vista previa cuenta las filas reparables y muestra conflictos sin escribir. La carga de demo se marca al concluir y no vuelve a restablecer existencias ni duplicar registros.

## Verificación y publicación

```bash
sudo docker compose ps
sudo docker compose logs --tail=50 app
curl -fsS http://localhost:8080/health
```

Ajusta el puerto al valor HTTP_PORT de tu `.env`. En una base nueva, `/health` debe informar 62 registros individuales; `registros` conserva su significado anterior y no incluye los consumibles. Los 150 consumibles se muestran en el dashboard.

Se verificaron localmente la sintaxis Python/Bash, la compilación de plantillas Jinja y las pruebas unitarias de agrupación y codificación. Las pruebas HTTP completas y de MySQL/Docker están en GitHub Actions; deben ejecutarse en un entorno desechable con Docker antes de considerar validada la integración. No ejecutes `tests/integracion.py` sobre datos activos. Publica la nueva imagen con `sudo bash scripts/publicar_imagen.sh USUARIO_DOCKERHUB v3.0.0` después de validar.

Los backups v3 incluyen consumibles y mínimos. Para retroceder a v2 utiliza un entorno separado y el respaldo anterior a la migración; no mezcles esquemas antiguos y nuevos sobre la base activa.
