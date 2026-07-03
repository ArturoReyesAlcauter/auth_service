-- Aplicar solo si la base de datos ya existe en PostgreSQL.
-- Este cambio evita errores al guardar refresh_token JWT con jti.
ALTER TABLE tokens_usuario ALTER COLUMN token TYPE VARCHAR(500);
