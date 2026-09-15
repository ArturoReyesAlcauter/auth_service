import asyncio
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.user import UsuarioPermisosDeltaCreate
from app.services import user_service


def run(coro):
    return asyncio.run(coro)


def test_delta_vacio_es_rechazado():
    data = UsuarioPermisosDeltaCreate()
    assert user_service._delta_tiene_operaciones(data) is False


def test_delta_detecta_solapamiento_de_accion():
    accion_id = uuid4()
    data = UsuarioPermisosDeltaCreate(
        accion_ids_agregar=[accion_id],
        accion_ids_quitar=[accion_id],
    )

    with pytest.raises(HTTPException) as exc_info:
        user_service._validar_delta_sin_solapamientos(data)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail["code"] == "PERMISSION_DELTA_CONFLICT"


def test_delta_con_operacion_es_valido():
    data = UsuarioPermisosDeltaCreate(
        grupo_ids_agregar=[uuid4()],
    )

    assert user_service._delta_tiene_operaciones(data) is True
    user_service._validar_delta_sin_solapamientos(data)


def test_autoedicion_con_cambio_marca_reautenticacion(monkeypatch):
    user_id = uuid4()
    grupo_id = uuid4()
    data = UsuarioPermisosDeltaCreate(grupo_ids_agregar=[grupo_id])

    fake_user = SimpleNamespace(id=user_id)
    fake_group = SimpleNamespace(id=grupo_id)

    class FakeUserQuery:
        def __await__(self):
            async def _resolve():
                return fake_user
            return _resolve().__await__()

    class FakeUserModel:
        @staticmethod
        def get_or_none(**kwargs):
            return FakeUserQuery()

    class FakeGroupQuery:
        def __await__(self):
            async def _resolve():
                return fake_group
            return _resolve().__await__()

    class FakeGroupModel:
        @staticmethod
        def get_or_none(**kwargs):
            return FakeGroupQuery()

    class FakeRelationModel:
        @staticmethod
        async def get_or_create(**kwargs):
            return SimpleNamespace(), True

    monkeypatch.setattr(user_service, "User", FakeUserModel)
    monkeypatch.setattr(user_service, "Grupo", FakeGroupModel)
    monkeypatch.setattr(user_service, "UsuarioGrupo", FakeRelationModel)
    monkeypatch.setattr(
        user_service,
        "validar_accion_en_grupo_o_super_admin",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        user_service,
        "resetear_ultima_sesion",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        user_service,
        "invalidar_sesiones_usuario",
        AsyncMock(return_value=fake_user),
    )
    monkeypatch.setattr(
        user_service,
        "obtener_permisos_usuario",
        AsyncMock(return_value={"grupos": []}),
    )

    # Llamamos a la función sin atravesar el wrapper transaccional para aislar
    # la regla de sesión. functools.wraps conserva __wrapped__ en @atomic().
    result = run(
        user_service.apply_user_permissions_delta.__wrapped__(
            user_id=user_id,
            data=data,
            current_user_id=user_id,
        )
    )

    assert result["total_operaciones"] == 1
    assert result["sesiones_invalidadas"] is True
    assert result["requiere_reautenticacion"] is True
    user_service.invalidar_sesiones_usuario.assert_awaited_once()
