"""Pruebas de fallo inyectado con SQLite temporal en memoria.

Ejecutar únicamente como prueba dirigida:
  python -m pytest -q tests/integration/test_user_service_atomicity_sqlite.py

No se conecta a PostgreSQL ni utiliza el DATABASE_URL del proyecto.
"""
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from tortoise import Tortoise
from tortoise.exceptions import IntegrityError

from app.models.user import (
    Accion,
    Grupo,
    Modulo,
    User,
    UsuarioAccion,
    UsuarioGrupo,
    UsuarioModulo,
)
from app.schemas.user import UserCreate, UsuarioAccionCreate, UsuarioModuloCreate
from app.services import user_service


async def preparar_base_en_memoria():
    # Se ignora deliberadamente app.core.config.TORTOISE_ORM.
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models.user"]},
    )
    await Tortoise.generate_schemas()


async def crear_usuario_prueba(suffix: str):
    return await User.create(
        nombre="Prueba",
        primer_apellido="Atomica",
        correo_electronico=f"atomicidad-{suffix}@example.com",
        curp="AAAB000101HDFCCC01",
        entidad_federativa_id=9,
    )


def test_rollback_crear_usuario_sin_membresia(monkeypatch):
    async def scenario():
        await preparar_base_en_memoria()
        try:
            grupo = await Grupo.create(nombre="GRUPO_PRUEBA")
            data = UserCreate(
                nombre="Prueba",
                primer_apellido="Atomica",
                correo_electronico="atomicidad-create@example.com",
                curp="AAAB000101HDFCCC01",
                entidad_federativa_id=9,
                grupo_id=grupo.id,
            )
            with monkeypatch.context() as m:
                m.setattr(
                    user_service,
                    "validar_accion_en_grupo_o_super_admin",
                    AsyncMock(return_value=None),
                )
                m.setattr(
                    user_service.UsuarioGrupo,
                    "get_or_create",
                    AsyncMock(side_effect=RuntimeError("fallo inyectado en membresia")),
                )
                with pytest.raises(RuntimeError, match="fallo inyectado"):
                    await user_service.create_user(data, creado_por=uuid4())
            assert not await User.filter(
                correo_electronico="atomicidad-create@example.com"
            ).exists(), "La creación sin membresía debe revertirse"
        finally:
            await Tortoise.close_connections()
    asyncio.run(scenario())


def test_rollback_asignar_modulo_revierte_membresia_previa(monkeypatch):
    async def scenario():
        await preparar_base_en_memoria()
        try:
            user = await crear_usuario_prueba("modulo")
            grupo = await Grupo.create(nombre="GRUPO_MODULO")
            modulo = await Modulo.create(nombre="MODULO_PRUEBA", grupo=grupo)
            with monkeypatch.context() as m:
                m.setattr(
                    user_service,
                    "validar_accion_en_grupo_o_super_admin",
                    AsyncMock(return_value=None),
                )
                m.setattr(
                    user_service.UsuarioModulo,
                    "create",
                    AsyncMock(side_effect=IntegrityError("fallo inyectado modulo")),
                )
                with pytest.raises(HTTPException) as error:
                    await user_service.assign_user_modulo(
                        user.id, UsuarioModuloCreate(modulo_id=modulo.id), uuid4()
                    )
                assert error.value.status_code == 409
            assert not await UsuarioGrupo.filter(
                usuario_id=user.id, grupo_id=grupo.id
            ).exists(), "La membresía temporal debe revertirse"
        finally:
            await Tortoise.close_connections()
    asyncio.run(scenario())


def test_rollback_asignar_accion_revierte_grupo_y_modulo(monkeypatch):
    async def scenario():
        await preparar_base_en_memoria()
        try:
            user = await crear_usuario_prueba("accion")
            grupo = await Grupo.create(nombre="GRUPO_ACCION")
            modulo = await Modulo.create(nombre="MODULO_ACCION", grupo=grupo)
            accion = await Accion.create(nombre="VER_ATOMICIDAD", modulo=modulo)
            with monkeypatch.context() as m:
                m.setattr(
                    user_service,
                    "validar_accion_en_grupo_o_super_admin",
                    AsyncMock(return_value=None),
                )
                m.setattr(
                    user_service.UsuarioAccion,
                    "create",
                    AsyncMock(side_effect=IntegrityError("fallo inyectado accion")),
                )
                with pytest.raises(HTTPException) as error:
                    await user_service.assign_user_accion(
                        user.id, UsuarioAccionCreate(accion_id=accion.id), uuid4()
                    )
                assert error.value.status_code == 409
            assert not await UsuarioGrupo.filter(usuario_id=user.id).exists()
            assert not await UsuarioModulo.filter(usuario_id=user.id).exists()
        finally:
            await Tortoise.close_connections()
    asyncio.run(scenario())


def test_rollback_retirar_grupo_restituye_acciones_eliminadas(monkeypatch):
    async def scenario():
        await preparar_base_en_memoria()
        try:
            user = await crear_usuario_prueba("retiro")
            grupo = await Grupo.create(nombre="GRUPO_RETIRO")
            modulo = await Modulo.create(nombre="MODULO_RETIRO", grupo=grupo)
            accion = await Accion.create(nombre="VER_RETIRO", modulo=modulo)
            await UsuarioGrupo.create(usuario_id=user.id, grupo_id=grupo.id)
            await UsuarioModulo.create(usuario_id=user.id, modulo_id=modulo.id)
            await UsuarioAccion.create(usuario_id=user.id, accion_id=accion.id)
            with monkeypatch.context() as m:
                m.setattr(
                    user_service,
                    "validar_accion_en_grupo_o_super_admin",
                    AsyncMock(return_value=None),
                )
                m.setattr(
                    user_service.UsuarioModulo,
                    "filter",
                    lambda **_kwargs: (_ for _ in ()).throw(
                        RuntimeError("fallo inyectado al quitar modulo")
                    ),
                )
                with pytest.raises(RuntimeError, match="fallo inyectado"):
                    await user_service.remove_user_grupo(user.id, grupo.id, uuid4())
            assert await UsuarioAccion.filter(
                usuario_id=user.id, accion_id=accion.id
            ).exists(), "La acción borrada temporalmente debe recuperarse"
            assert await UsuarioModulo.filter(usuario_id=user.id, modulo_id=modulo.id).exists()
            assert await UsuarioGrupo.filter(usuario_id=user.id, grupo_id=grupo.id).exists()
        finally:
            await Tortoise.close_connections()
    asyncio.run(scenario())
