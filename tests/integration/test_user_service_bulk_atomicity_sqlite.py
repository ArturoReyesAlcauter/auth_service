"""Transacciones masivas aisladas en SQLite :memory:; no lee DATABASE_URL.

El correo es SIEMPRE falso (mock), sin conexiones SMTP.
Ejecutar: python -m pytest -q tests/integration/test_user_service_bulk_atomicity_sqlite.py
"""
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from tortoise import Tortoise

from app.models.user import (
    Accion, Grupo, Modulo, TokenUsuario, UltimaSesion, User,
    UsuarioAccion, UsuarioGrupo, UsuarioModulo,
)
from app.schemas.user import UsuarioPermisosMasivosCreate
from app.services import user_service


async def preparar():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models.user"]},
    )
    await Tortoise.generate_schemas()
    usuario = await User.create(
        nombre="Prueba", primer_apellido="Masiva",
        correo_electronico="bulk-atomic@example.com",
        curp="AAAB000101HDFCCC01",
    )
    grupo = await Grupo.create(nombre="GRUPO_BULK")
    modulo = await Modulo.create(nombre="MODULO_BULK", grupo=grupo)
    accion = await Accion.create(nombre="VER_BULK", modulo=modulo)
    datos = UsuarioPermisosMasivosCreate(
        grupo_id=grupo.id, modulo_ids=[modulo.id], accion_ids=[accion.id]
    )
    return usuario, grupo, modulo, accion, datos


async def contar_asignaciones(usuario):
    return (
        await UsuarioGrupo.filter(usuario_id=usuario.id).count(),
        await UsuarioModulo.filter(usuario_id=usuario.id).count(),
        await UsuarioAccion.filter(usuario_id=usuario.id).count(),
    )


def mocks(monkeypatch, *, correo=None):
    monkeypatch.setattr(
        user_service, "validar_accion_en_grupo_o_super_admin",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        user_service, "usuario_es_super_admin",
        AsyncMock(return_value=True),
    )
    smtp = correo or AsyncMock(return_value=None)
    monkeypatch.setattr(user_service, "enviar_correo_activacion_usuario", smtp)
    return smtp


def test_asignacion_masiva_confirma_todo_y_envia_una_vez(monkeypatch):
    async def escenario():
        usuario, _, _, _, datos = await preparar()
        try:
            smtp = mocks(monkeypatch)
            resultado = await user_service.assign_user_permisos_masivos(
                usuario.id, datos, uuid4()
            )
            assert await contar_asignaciones(usuario) == (1, 1, 1)
            assert resultado["grupos_asignados"] == 1
            assert resultado["modulos_asignados"] == 1
            assert resultado["acciones_asignadas"] == 1
            assert resultado["correo_bienvenida_enviado"] is True
            assert await TokenUsuario.filter(usuario_id=usuario.id, tipo="CREAR_CONTRASENA").count() == 1
            assert (await User.get(id=usuario.id)).token_version == 2
            assert await UltimaSesion.filter(usuario_id=usuario.id).exists()
            smtp.assert_awaited_once()
        finally:
            await Tortoise.close_connections()
    asyncio.run(escenario())


def test_rollback_si_falla_el_ultimo_permiso(monkeypatch):
    async def escenario():
        usuario, _, _, _, datos = await preparar()
        try:
            smtp = mocks(monkeypatch)
            with monkeypatch.context() as m:
                m.setattr(
                    user_service.UsuarioAccion,
                    "get_or_create",
                    AsyncMock(side_effect=RuntimeError("fallo inyectado en accion")),
                )
                with pytest.raises(RuntimeError, match="fallo inyectado"):
                    await user_service.assign_user_permisos_masivos(
                        usuario.id, datos, uuid4()
                    )
            assert await contar_asignaciones(usuario) == (0, 0, 0)
            assert (await User.get(id=usuario.id)).token_version == 1
            assert await TokenUsuario.filter(usuario_id=usuario.id).count() == 0
            smtp.assert_not_awaited()
        finally:
            await Tortoise.close_connections()
    asyncio.run(escenario())


def test_rollback_si_falla_generacion_token_despues_de_guardar(monkeypatch):
    async def escenario():
        usuario, _, _, _, datos = await preparar()
        try:
            smtp = mocks(monkeypatch)
            with monkeypatch.context() as m:
                m.setattr(
                    user_service,
                    "generar_token_creacion_password",
                    AsyncMock(side_effect=RuntimeError("fallo token inyectado")),
                )
                with pytest.raises(RuntimeError, match="fallo token"):
                    await user_service.assign_user_permisos_masivos(
                        usuario.id, datos, uuid4()
                    )
            assert await contar_asignaciones(usuario) == (0, 0, 0)
            assert (await User.get(id=usuario.id)).token_version == 1
            assert not await UltimaSesion.filter(usuario_id=usuario.id).exists()
            assert await TokenUsuario.filter(usuario_id=usuario.id).count() == 0
            smtp.assert_not_awaited()
        finally:
            await Tortoise.close_connections()
    asyncio.run(escenario())


def test_fallo_smtp_no_revierte_permisos_ni_duplica_en_reintento(monkeypatch):
    async def escenario():
        usuario, _, _, _, datos = await preparar()
        try:
            smtp = mocks(monkeypatch, correo=AsyncMock(side_effect=RuntimeError("SMTP simulado")))
            resultado = await user_service.assign_user_permisos_masivos(
                usuario.id, datos, uuid4()
            )
            assert resultado["correo_bienvenida_enviado"] is False
            assert await contar_asignaciones(usuario) == (1, 1, 1)
            assert await TokenUsuario.filter(usuario_id=usuario.id, tipo="CREAR_CONTRASENA").count() == 1
            assert (await User.get(id=usuario.id)).token_version == 2
            smtp.assert_awaited_once()
            otro = await user_service.assign_user_permisos_masivos(
                usuario.id, datos, uuid4()
            )
            assert (otro["grupos_asignados"], otro["modulos_asignados"], otro["acciones_asignadas"]) == (0, 0, 0)
            assert otro["correo_bienvenida_enviado"] is False
            assert await contar_asignaciones(usuario) == (1, 1, 1)
            assert (await User.get(id=usuario.id)).token_version == 2
            assert await TokenUsuario.filter(usuario_id=usuario.id, tipo="CREAR_CONTRASENA").count() == 1
            smtp.assert_awaited_once()
        finally:
            await Tortoise.close_connections()
    asyncio.run(escenario())


def test_cuenta_con_password_no_genera_token_ni_correo(monkeypatch):
    async def escenario():
        usuario, _, _, _, datos = await preparar()
        try:
            await User.filter(id=usuario.id).update(contrasena_hasheada="hash-de-prueba")
            smtp = mocks(monkeypatch)
            resultado = await user_service.assign_user_permisos_masivos(
                usuario.id, datos, uuid4()
            )
            assert resultado["correo_bienvenida_enviado"] is False
            assert await contar_asignaciones(usuario) == (1, 1, 1)
            assert await TokenUsuario.filter(usuario_id=usuario.id).count() == 0
            smtp.assert_not_awaited()
        finally:
            await Tortoise.close_connections()
    asyncio.run(escenario())
