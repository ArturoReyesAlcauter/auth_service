from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'registros_principales'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'grupos'
            ) THEN
                ALTER TABLE "registros_principales" RENAME TO "grupos";
            END IF;
        END $$;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'modulos'
                AND column_name = 'registro_principal_id'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'modulos'
                AND column_name = 'grupo_id'
            ) THEN
                ALTER TABLE "modulos" RENAME COLUMN "registro_principal_id" TO "grupo_id";
            END IF;
        END $$;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'usuario_registros'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'usuario_grupos'
            ) THEN
                ALTER TABLE "usuario_registros" RENAME TO "usuario_grupos";
            END IF;
        END $$;

        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'usuario_grupos'
                AND column_name = 'registro_id'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'usuario_grupos'
                AND column_name = 'grupo_id'
            ) THEN
                ALTER TABLE "usuario_grupos" RENAME COLUMN "registro_id" TO "grupo_id";
            END IF;
        END $$;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
)
