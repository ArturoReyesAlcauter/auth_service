from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "usuarios"
        ADD COLUMN IF NOT EXISTS "token_version" INT NOT NULL DEFAULT 1;

        COMMENT ON COLUMN "usuarios"."token_version" IS 'Incrementa para invalidar todos los tokens activos de este usuario';
    """

async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "usuarios"
        DROP COLUMN IF EXISTS "token_version";
    """

MODELS_STATE = (
    "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"
    "MZ"
)
