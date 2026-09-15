import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services import super_admin_guard as guard


def run(coro):
    return asyncio.run(coro)


def assert_error(exc_info, status_code: int, code: str):
    exc = exc_info.value
    assert isinstance(exc, HTTPException)
    assert exc.status_code == status_code
    assert exc.detail["code"] == code


def test_solo_super_admin_puede_retirar_super_admin(monkeypatch):
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin",
        AsyncMock(return_value=False),
    )

    with pytest.raises(HTTPException) as exc_info:
        run(
            guard.validar_retiro_super_admin(
                target_user_id=uuid4(),
                current_user_id=uuid4(),
            )
        )

    assert_error(exc_info, 403, "SUPER_ADMIN_REQUIRED")


def test_super_admin_no_puede_retirarse_a_si_mismo(monkeypatch):
    user_id = uuid4()
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin",
        AsyncMock(return_value=True),
    )

    with pytest.raises(HTTPException) as exc_info:
        run(
            guard.validar_retiro_super_admin(
                target_user_id=user_id,
                current_user_id=user_id,
            )
        )

    assert_error(exc_info, 403, "SELF_SUPER_ADMIN_REMOVAL_FORBIDDEN")


def test_no_se_puede_retirar_ultimo_super_admin_activo(monkeypatch):
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin_activo",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        guard,
        "contar_super_admin_activos",
        AsyncMock(return_value=1),
    )

    with pytest.raises(HTTPException) as exc_info:
        run(
            guard.validar_retiro_super_admin(
                target_user_id=uuid4(),
                current_user_id=uuid4(),
            )
        )

    assert_error(exc_info, 409, "LAST_ACTIVE_SUPER_ADMIN_REQUIRED")


def test_se_puede_retirar_super_admin_si_queda_otro_activo(monkeypatch):
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin_activo",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        guard,
        "contar_super_admin_activos",
        AsyncMock(return_value=2),
    )

    run(
        guard.validar_retiro_super_admin(
            target_user_id=uuid4(),
            current_user_id=uuid4(),
        )
    )


def test_bloquea_auto_desactivacion(monkeypatch):
    user_id = uuid4()

    with pytest.raises(HTTPException) as exc_info:
        run(
            guard.validar_cambio_estatus_protegido(
                target_user_id=user_id,
                current_user_id=user_id,
                nuevo_estatus_nombre="Inactivo",
            )
        )

    assert_error(exc_info, 403, "SELF_DEACTIVATION_FORBIDDEN")


def test_permite_mantenerse_activo_a_si_mismo():
    user_id = uuid4()
    run(
        guard.validar_cambio_estatus_protegido(
            target_user_id=user_id,
            current_user_id=user_id,
            nuevo_estatus_nombre="Activo",
        )
    )


def test_bloquea_desactivar_ultimo_super_admin_activo(monkeypatch):
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin_activo",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        guard,
        "contar_super_admin_activos",
        AsyncMock(return_value=1),
    )

    with pytest.raises(HTTPException) as exc_info:
        run(
            guard.validar_cambio_estatus_protegido(
                target_user_id=uuid4(),
                current_user_id=uuid4(),
                nuevo_estatus_nombre="Inactivo",
            )
        )

    assert_error(exc_info, 409, "LAST_ACTIVE_SUPER_ADMIN_REQUIRED")


def test_inactividad_no_revoca_ultimo_super_admin(monkeypatch):
    monkeypatch.setattr(
        guard,
        "usuario_es_super_admin_activo",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        guard,
        "contar_super_admin_activos",
        AsyncMock(return_value=1),
    )

    with pytest.raises(HTTPException) as exc_info:
        run(
            guard.validar_revocacion_total_por_inactividad(
                user_id=uuid4(),
            )
        )

    assert_error(exc_info, 409, "LAST_ACTIVE_SUPER_ADMIN_REQUIRED")
