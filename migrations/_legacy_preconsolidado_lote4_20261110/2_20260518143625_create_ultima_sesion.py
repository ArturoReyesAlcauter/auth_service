from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "ultima_sesion" (
    "id" UUID NOT NULL PRIMARY KEY,
    "fecha_inicio_sesion" TIMESTAMPTZ,
    "fecha_creacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "fecha_actualizacion" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "usuario_id" UUID NOT NULL UNIQUE REFERENCES "usuarios" ("id") ON DELETE CASCADE
);
"""

async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "ultima_sesion";
"""


MODELS_STATE = (
    "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"
)
