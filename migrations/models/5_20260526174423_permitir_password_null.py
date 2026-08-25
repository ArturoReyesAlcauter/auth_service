from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "usuarios" ALTER COLUMN "contrasena_hasheada" DROP NOT NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "usuarios" ALTER COLUMN "contrasena_hasheada" SET NOT NULL;"""


MODELS_STATE = (
    "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"
)
