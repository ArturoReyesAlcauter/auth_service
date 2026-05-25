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
        END $$;
    """