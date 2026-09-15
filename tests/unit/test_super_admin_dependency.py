import asyncio
import os
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_INITIAL_PASSWORD", "TestPassword123!")
os.environ.setdefault("CRONOS_TEST_PASSWORD", "TestPassword123!")

from app.api import dependencies


def run(coro):
    return asyncio.run(coro)


def credentials():
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-token",
    )


def test_super_admin_es_bypass_global(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda _: {"acciones": ["SUPER_ADMIN"]},
    )

    current_user = SimpleNamespace(id="admin")
    dependency = dependencies.requiere_accion("ACTUALIZAR_USUARIO")

    result = run(
        dependency(
            credentials=credentials(),
            current_user=current_user,
        )
    )

    assert result is current_user


def test_usuario_sin_accion_es_rechazado(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "decode_access_token",
        lambda _: {"acciones": ["VER_USUARIOS"]},
    )

    dependency = dependencies.requiere_accion("ACTUALIZAR_USUARIO")

    with pytest.raises(HTTPException) as exc_info:
        run(
            dependency(
                credentials=credentials(),
                current_user=SimpleNamespace(id="user"),
            )
        )

    assert exc_info.value.status_code == 403
