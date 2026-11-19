"""Proteccion del seed inicial: pruebas sin acceso a PostgreSQL."""
import asyncio
import inspect
from unittest.mock import AsyncMock

import pytest

import seed


MODELOS_PROTEGIDOS = (
    "User",
    "Grupo",
    "Modulo",
    "Accion",
    "UsuarioGrupo",
    "UsuarioModulo",
    "UsuarioAccion",
)


def preparar_modelos(monkeypatch, *, ocupado=None):
    mocks = {}
    for nombre in MODELOS_PROTEGIDOS:
        consulta = AsyncMock(return_value=(nombre == ocupado))
        monkeypatch.setattr(getattr(seed, nombre), "exists", consulta)
        mocks[nombre] = consulta
    return mocks


@pytest.mark.parametrize("ocupado", MODELOS_PROTEGIDOS)
def test_seed_rechaza_bases_pobladas_antes_de_escribir(monkeypatch, ocupado):
    preparar_modelos(monkeypatch, ocupado=ocupado)
    with pytest.raises(RuntimeError, match="SEED_BLOQUEADO_BASE_POBLADA"):
        asyncio.run(seed.validar_seed_solo_bootstrap())


def test_seed_permite_catalogo_totalmente_vacio(monkeypatch):
    consultas = preparar_modelos(monkeypatch)
    asyncio.run(seed.validar_seed_solo_bootstrap())
    for consulta in consultas.values():
        consulta.assert_awaited_once_with()


def test_main_comprueba_bootstrap_antes_de_eliminar_o_asignar():
    codigo = inspect.getsource(seed.main)
    guardia = codigo.index("await validar_seed_solo_bootstrap()")
    primer_delete = codigo.index("await eliminar_catalogo_legacy()")
    admin = codigo.index("admin = await User.get_or_none(")
    assert guardia < primer_delete < admin
