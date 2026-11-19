"""Pruebas estructurales sin DB; no sustituyen integración PostgreSQL."""

import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "seed.py"


def _module_definitions():
    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "main")
    placements = {}
    for node in ast.walk(main):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "asegurar_modulo":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                placements[node.args[1].value] = ast.unparse(node.args[0])
    return placements


def test_seed_coloca_modulos_por_dominio():
    actual = _module_definitions()
    assert actual["BITACORA_ATENCIONES"] == "grupo_mesa_ayuda"
    assert actual["REPORTES_INDICADORES"] == "grupo_mesa_ayuda"
    assert actual["ADMINISTRACION_USUARIOS"] == "grupo_configuracion"
    assert actual["ADMINISTRACION_PERMISOS"] == "grupo_configuracion"


def test_seed_valida_migracion_antes_de_escrituras():
    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "main")
    first_operation = main.body[1].body[0]
    assert isinstance(first_operation, ast.Expr)
    assert isinstance(first_operation.value, ast.Await)
    assert isinstance(first_operation.value.value, ast.Call)
    assert first_operation.value.value.func.id == "validar_seed_solo_bootstrap"

    second_operation = main.body[1].body[1]
    assert isinstance(second_operation, ast.Expr)
    assert isinstance(second_operation.value, ast.Await)
    assert isinstance(second_operation.value.value, ast.Call)
    assert second_operation.value.value.func.id == "validar_separacion_configuracion"


def test_guard_rechaza_catalogo_legacy(monkeypatch):
    class FakeQuery:
        async def exists(self):
            return True
    class FakeModulo:
        @staticmethod
        def filter(**kwargs):
            assert kwargs["grupo__nombre"] == "MESA_AYUDA"
            return FakeQuery()

    tree = ast.parse(SEED.read_text(encoding="utf-8"))
    guard = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "validar_separacion_configuracion")
    mod = ast.fix_missing_locations(ast.Module(body=[guard],type_ignores=[]))
    ns = {"Modulo": FakeModulo, "GRUPO_MESA_AYUDA": "MESA_AYUDA"}
    exec(compile(mod,"<guard>","exec"),ns)
    with pytest.raises(RuntimeError,match="No ejecutes el seed"):
        asyncio.run(ns["validar_separacion_configuracion"]())
