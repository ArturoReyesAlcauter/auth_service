from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cat_estatus_usuarios" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(50) NOT NULL
);
COMMENT ON COLUMN "cat_estatus_usuarios"."nombre" IS 'Activo, En Proceso, Inactivo';
CREATE TABLE IF NOT EXISTS "grupos" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "descripcion" VARCHAR(200)
);
COMMENT ON COLUMN "grupos"."nombre" IS 'Ej: VF, MH, MP, RNCAS';
CREATE TABLE IF NOT EXISTS "cat_instancias" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "siglas" VARCHAR(20) NOT NULL
);
COMMENT ON COLUMN "cat_instancias"."nombre" IS 'Ej: Sistema Nacional DIF, Procuraduría...';
COMMENT ON COLUMN "cat_instancias"."siglas" IS 'Ej: SNDIF, PFPNNA, COMAR, UAPV';
CREATE TABLE IF NOT EXISTS "modulos" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "descripcion" VARCHAR(200),
    "grupo_id" UUID NOT NULL REFERENCES "grupos" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "modulos"."nombre" IS 'Ej: Datos Generales, NNA, Medidas, Seguimiento';
CREATE TABLE IF NOT EXISTS "acciones" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(50) NOT NULL,
    "descripcion" VARCHAR(200),
    "modulo_id" UUID NOT NULL REFERENCES "modulos" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "acciones"."nombre" IS 'Ej: LEER_NNA, CREAR_NNA, EDITAR_NNA';
CREATE TABLE IF NOT EXISTS "usuarios" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "primer_apellido" VARCHAR(100) NOT NULL,
    "segundo_apellido" VARCHAR(100),
    "correo_electronico" VARCHAR(200) NOT NULL UNIQUE,
    "curp" VARCHAR(18) NOT NULL UNIQUE,
    "entidad_federativa_id" INT,
    "numero_telefono" VARCHAR(15),
    "contrasena_hasheada" VARCHAR(200),
    "token_version" INT NOT NULL DEFAULT 1,
    "is_2fa_enabled" BOOL NOT NULL DEFAULT False,
    "totp_secret" VARCHAR(100),
    "creado_por" UUID,
    "intentos_login" INT NOT NULL DEFAULT 0,
    "fecha_correo_verificado" TIMESTAMPTZ,
    "fecha_creacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_actualizacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "estatus_id" INT REFERENCES "cat_estatus_usuarios" ("id") ON DELETE SET NULL,
    "instancia_id" INT REFERENCES "cat_instancias" ("id") ON DELETE SET NULL
);
COMMENT ON COLUMN "usuarios"."entidad_federativa_id" IS 'ID de la entidad federativa obtenido desde el catálogo externo';
COMMENT ON COLUMN "usuarios"."token_version" IS 'Incrementa para invalidar todos los tokens activos de este usuario';
CREATE TABLE IF NOT EXISTS "tokens_usuario" (
    "id" UUID NOT NULL PRIMARY KEY,
    "token" VARCHAR(500) NOT NULL UNIQUE,
    "tipo" VARCHAR(50) NOT NULL,
    "fecha_expiracion" TIMESTAMPTZ NOT NULL,
    "fecha_creacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "tokens_usuario"."tipo" IS 'VERIFICACION_CORREO, RECUPERACION_CONTRASENA, REFRESH_TOKEN, REDIRECT_CODE';
CREATE TABLE IF NOT EXISTS "ultima_sesion" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_inicio_sesion" TIMESTAMPTZ,
    "fecha_creacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_actualizacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuario_id" UUID NOT NULL UNIQUE REFERENCES "usuarios" ("id") ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS "usuario_acciones" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_asignacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "accion_id" UUID NOT NULL REFERENCES "acciones" ("id") ON DELETE CASCADE,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_usuario_acc_usuario_963f40" UNIQUE ("usuario_id", "accion_id")
);
CREATE TABLE IF NOT EXISTS "usuario_grupos" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_asignacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "grupo_id" UUID NOT NULL REFERENCES "grupos" ("id") ON DELETE CASCADE,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_usuario_gru_usuario_d6502a" UNIQUE ("usuario_id", "grupo_id")
);
CREATE TABLE IF NOT EXISTS "usuario_modulos" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_asignacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "modulo_id" UUID NOT NULL REFERENCES "modulos" ("id") ON DELETE CASCADE,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_usuario_mod_usuario_237e13" UNIQUE ("usuario_id", "modulo_id")
);
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "ZylWQz8gJXh579c6hh+f5/8zc9/Q=="
)
