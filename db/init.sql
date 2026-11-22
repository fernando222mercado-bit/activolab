-- Inventario genérico de activos. DATOS 100% FICTICIOS para uso academico.
-- Este script se ejecuta SOLO al crear por primera vez el volumen vacio de MySQL.

CREATE TABLE IF NOT EXISTS tipos_equipo (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(90) NOT NULL UNIQUE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS estados (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(60) NOT NULL UNIQUE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS equipos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    codigo_inventario VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(180) NOT NULL,
    tipo_id INT NOT NULL,
    marca VARCHAR(80),
    modelo VARCHAR(80),
    serie VARCHAR(60) NOT NULL UNIQUE,
    estado_id INT NOT NULL,
    ubicacion VARCHAR(120) NOT NULL,
    responsable VARCHAR(120) NOT NULL DEFAULT 'Sin asignar',
    fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_equipo_tipo FOREIGN KEY (tipo_id) REFERENCES tipos_equipo(id),
    CONSTRAINT fk_equipo_estado FOREIGN KEY (estado_id) REFERENCES estados(id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS movimientos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    equipo_id INT NOT NULL,
    accion VARCHAR(45) NOT NULL,
    estado_anterior VARCHAR(60),
    estado_nuevo VARCHAR(60),
    ubicacion_anterior VARCHAR(120),
    ubicacion_nueva VARCHAR(120),
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_mov_equipo FOREIGN KEY (equipo_id) REFERENCES equipos(id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

INSERT INTO tipos_equipo (nombre) VALUES
('Computadora'), ('Monitor'), ('Impresora'), ('Equipo de red'),
('Herramienta'), ('Mobiliario'), ('Servidor'), ('UPS'), ('Periférico'), ('Otro');

INSERT INTO estados (nombre) VALUES
('Disponible'), ('Asignado'), ('En mantenimiento'), ('En reparación'), ('Reservado'), ('Baja');

INSERT INTO equipos (codigo_inventario, descripcion, tipo_id, marca, modelo, serie, estado_id, ubicacion, responsable) VALUES
('INV-001','Computadora de escritorio',1,'Marca demo A','PC-100','SN-DEMO-001',1,'Almacén / Estante A1','Sin asignar'),
('INV-002','Monitor de 24 pulgadas',2,'Marca demo B','MON-24','SN-DEMO-002',2,'Oficina 1','Usuario de ejemplo 01'),
('INV-003','Impresora multifunción',3,'Marca demo C','IMP-24','SN-DEMO-003',1,'Almacén / Estante B2','Sin asignar'),
('INV-004','Switch de 24 puertos',4,'Marca demo D','SW-24','SN-DEMO-004',5,'Almacén / Estante C3','Sin asignar'),
('INV-005','Taladro eléctrico',5,'Marca demo E','HER-5','SN-DEMO-005',3,'Mesa de mantenimiento','Usuario de ejemplo 02'),
('INV-006','Silla de oficina',6,'Marca demo F','MOB-1','SN-DEMO-006',1,'Almacén / Área D1','Sin asignar');
