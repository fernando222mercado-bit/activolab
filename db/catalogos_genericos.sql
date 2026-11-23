SET NAMES utf8mb4;
-- Opcional para instalaciones existentes. No elimina ni cambia categorías o equipos.
INSERT IGNORE INTO tipos_equipo (nombre) VALUES
('Computadora'), ('Monitor'), ('Impresora'), ('Equipo de red'),
('Herramienta'), ('Mobiliario'), ('Servidor'), ('UPS'), ('Periférico'), ('Otro');
