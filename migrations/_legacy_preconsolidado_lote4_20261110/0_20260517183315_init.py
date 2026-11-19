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
    "entidad_federativa_id" INT,
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
COMMENT ON COLUMN "usuarios"."entidad_federativa_id" IS 'ID de la entidad federativa obtenido desde el catálogo externo';
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
)
