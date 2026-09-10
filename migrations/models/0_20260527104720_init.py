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
    "contrasena_hasheada" VARCHAR(200) NOT NULL,
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
    "token" VARCHAR(200) NOT NULL UNIQUE,
    "tipo" VARCHAR(50) NOT NULL,
    "fecha_expiracion" TIMESTAMPTZ NOT NULL,
    "fecha_creacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "tokens_usuario"."tipo" IS 'VERIFICACION_CORREO, RECUPERACION_CONTRASENA';
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
)
