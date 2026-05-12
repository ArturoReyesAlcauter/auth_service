import asyncio

from tortoise import Tortoise
from app.core.config import TORTOISE_ORM


SQL = """
DROP TABLE IF EXISTS usuario_acciones CASCADE;
DROP TABLE IF EXISTS usuario_modulos CASCADE;
DROP TABLE IF EXISTS usuario_registros CASCADE;
DROP TABLE IF EXISTS tokens_usuario CASCADE;
DROP TABLE IF EXISTS acciones CASCADE;
DROP TABLE IF EXISTS modulos CASCADE;
DROP TABLE IF EXISTS registros_principales CASCADE;

DROP TABLE IF EXISTS user_access CASCADE;
DROP TABLE IF EXISTS rol_permisos CASCADE;
DROP TABLE IF EXISTS cat_roles CASCADE;
DROP TABLE IF EXISTS cat_permisos CASCADE;
DROP TABLE IF EXISTS cat_registros CASCADE;

DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS cat_instancias CASCADE;
DROP TABLE IF EXISTS cat_estatus_usuarios CASCADE;
DROP TABLE IF EXISTS aerich CASCADE;
"""


async def main():
    await Tortoise.init(config=TORTOISE_ORM)
    conn = Tortoise.get_connection("default")
    await conn.execute_script(SQL)
    await Tortoise.close_connections()
    print("Base de datos limpiada correctamente.")


if __name__ == "__main__":
    asyncio.run(main())