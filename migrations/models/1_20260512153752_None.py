from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "cat_estatus_usuarios" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(50) NOT NULL
);
COMMENT ON COLUMN "cat_estatus_usuarios"."nombre" IS 'Activo, En Proceso, Inactivo';
CREATE TABLE IF NOT EXISTS "cat_instancias" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "siglas" VARCHAR(20) NOT NULL
);
COMMENT ON COLUMN "cat_instancias"."nombre" IS 'Ej: Sistema Nacional DIF, Procuraduría...';
COMMENT ON COLUMN "cat_instancias"."siglas" IS 'Ej: SNDIF, PFPNNA, COMAR, UAPV';
CREATE TABLE IF NOT EXISTS "registros_principales" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "descripcion" VARCHAR(200)
);
COMMENT ON COLUMN "registros_principales"."nombre" IS 'Ej: VF, MH, MP, RNCAS';
CREATE TABLE IF NOT EXISTS "modulos" (
    "id" UUID NOT NULL PRIMARY KEY,
    "nombre" VARCHAR(100) NOT NULL,
    "descripcion" VARCHAR(200),
    "registro_principal_id" UUID NOT NULL REFERENCES "registros_principales" ("id") ON DELETE CASCADE
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
    "numero_telefono" VARCHAR(15),
    "contrasena_hasheada" VARCHAR(200) NOT NULL,
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
CREATE TABLE IF NOT EXISTS "tokens_usuario" (
    "id" UUID NOT NULL PRIMARY KEY,
    "token" VARCHAR(200) NOT NULL UNIQUE,
    "tipo" VARCHAR(50) NOT NULL,
    "fecha_expiracion" TIMESTAMPTZ NOT NULL,
    "fecha_creacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "tokens_usuario"."tipo" IS 'VERIFICACION_CORREO, RECUPERACION_CONTRASENA';
CREATE TABLE IF NOT EXISTS "usuario_acciones" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_asignacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "accion_id" UUID NOT NULL REFERENCES "acciones" ("id") ON DELETE CASCADE,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_usuario_acc_usuario_963f40" UNIQUE ("usuario_id", "accion_id")
);
CREATE TABLE IF NOT EXISTS "usuario_modulos" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_asignacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "modulo_id" UUID NOT NULL REFERENCES "modulos" ("id") ON DELETE CASCADE,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_usuario_mod_usuario_237e13" UNIQUE ("usuario_id", "modulo_id")
);
CREATE TABLE IF NOT EXISTS "usuario_registros" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_asignacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "registro_id" UUID NOT NULL REFERENCES "registros_principales" ("id") ON DELETE CASCADE,
    "usuario_id" UUID NOT NULL REFERENCES "usuarios" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_usuario_reg_usuario_cf8347" UNIQUE ("usuario_id", "registro_id")
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
    "4O4Ny4//AZH5n7E="
)
