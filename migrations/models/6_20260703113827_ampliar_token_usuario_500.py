from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        COMMENT ON COLUMN "tokens_usuario"."tipo" IS 'VERIFICACION_CORREO, RECUPERACION_CONTRASENA, REFRESH_TOKEN, REDIRECT_CODE';
        ALTER TABLE "tokens_usuario" ALTER COLUMN "token" TYPE VARCHAR(500) USING "token"::VARCHAR(500);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        COMMENT ON COLUMN "tokens_usuario"."tipo" IS 'VERIFICACION_CORREO, RECUPERACION_CONTRASENA';
        ALTER TABLE "tokens_usuario" ALTER COLUMN "token" TYPE VARCHAR(200) USING "token"::VARCHAR(200);"""


MODELS_STATE = (
    "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"
    "ZylWQz8gJXh579c6hh+f5/8zc9/Q=="
)
