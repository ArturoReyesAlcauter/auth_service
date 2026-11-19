"""Pruebas del contrato de bloqueo. No utilizan una base real."""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import super_admin_guard as guard


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.order_verified = False
        self.lock_verified = False

    def order_by(self, field):
        assert field == "id"
        self.order_verified = True
        return self

    def select_for_update(self, *, no_key):
        assert no_key is True
        self.lock_verified = True
        return self

    def __await__(self):
        async def run():
            return self.rows
        return run().__await__()


def test_bloquea_unico_registro_activo_con_no_key_update(monkeypatch):
    fake = FakeQuery([SimpleNamespace(id=1)])
    fake_filter = MagicMock(return_value=fake)
    monkeypatch.setattr(guard.EstatusUsuario, "filter", fake_filter)

    asyncio.run(guard.bloquear_mutacion_super_admin())

    fake_filter.assert_called_once_with(nombre__iexact="activo")
    assert fake.order_verified and fake.lock_verified


@pytest.mark.parametrize("cantidad", [0, 2])
def test_bloqueo_falla_cerrado_si_catalogo_ambiguo(monkeypatch, cantidad):
    fake = FakeQuery([SimpleNamespace(id=i + 1) for i in range(cantidad)])
    monkeypatch.setattr(guard.EstatusUsuario, "filter", lambda **_: fake)

    with pytest.raises(HTTPException) as error:
        asyncio.run(guard.bloquear_mutacion_super_admin())

    assert fake.order_verified and fake.lock_verified
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "ACTIVE_STATUS_MISSING"
