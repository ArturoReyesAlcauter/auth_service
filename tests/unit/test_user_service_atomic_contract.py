"""Contrato estático: escrituras individuales de Auth deben ser atómicas.

No abre conexiones ni modifica datos reales.
"""
import ast
from pathlib import Path

import pytest


SERVICE_PATH = (
    Path(__file__).resolve().parents[2] / "app" / "services" / "user_service.py"
)
ATOMIC_FUNCTIONS = (
    "create_user",
    "assign_user_grupo",
    "assign_user_modulo",
    "assign_user_accion",
    "remove_user_grupo",
    "remove_user_modulo",
    "remove_user_accion",
)


@pytest.mark.parametrize("function_name", ATOMIC_FUNCTIONS)
def test_operacion_individual_es_transaccional(function_name):
    module = ast.parse(SERVICE_PATH.read_text(encoding="utf-8-sig"))
    matches = [
        node
        for node in module.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == function_name
    ]
    assert len(matches) == 1
    operation = matches[0]
    assert any(
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Name)
        and decorator.func.id == "atomic"
        and not decorator.args
        and not decorator.keywords
        for decorator in operation.decorator_list
    ), f"{function_name} debe usar @atomic()"


def test_delta_continua_transaccional():
    module = ast.parse(SERVICE_PATH.read_text(encoding="utf-8-sig"))
    operation = next(
        n for n in module.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "apply_user_permissions_delta"
    )
    assert any(
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Name)
        and decorator.func.id == "atomic"
        for decorator in operation.decorator_list
    )


def test_asignacion_masiva_no_incluye_correo_en_transaccion():
    module = ast.parse(SERVICE_PATH.read_text(encoding="utf-8-sig"))
    operation = next(
        n for n in module.body
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "assign_user_permisos_masivos"
    )
    assert not operation.decorator_list, (
        "La asignación masiva contiene envío de correo; requiere una solución "
        "transaccional específica antes de decorarla."
    )
