"""Contratos estructurales: no requieren BD ni conexión externa."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "app/services/user_service.py"
SESSION = ROOT / "app/services/session_service.py"
GUARD = ROOT / "app/services/super_admin_guard.py"


def function(path: Path, name: str) -> ast.AsyncFunctionDef:
    module = ast.parse(path.read_text(encoding="utf-8-sig"))
    matches = [
        node for node in ast.walk(module)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    ]
    assert len(matches) == 1, f"Se esperaba exactamente una función {name}"
    return matches[0]


def calls_in_order(node):
    calls = []
    for obj in ast.walk(node):
        if isinstance(obj, ast.Await) and isinstance(obj.value, ast.Call):
            f = obj.value.func
            if isinstance(f, ast.Name):
                calls.append((obj.lineno, f.id))
    return sorted(calls)


def assert_lock_before_validation(node, validation):
    calls = calls_in_order(node)
    locks = [n for n, name in calls if name == "bloquear_mutacion_super_admin"]
    checks = [n for n, name in calls if name == validation]
    assert locks and checks
    assert locks[0] < checks[0], "Se debe bloquear antes de validar"


def has_atomic_decorator(node):
    return any(
        isinstance(d, ast.Call)
        and isinstance(d.func, ast.Name)
        and d.func.id == "atomic"
        for d in node.decorator_list
    )


@pytest.mark.parametrize("name", [
    "remove_user_grupo", "remove_user_modulo", "remove_user_accion",
    "apply_user_permissions_delta",
])
def test_revocaciones_serializadas_y_atomicas(name):
    node = function(SERVICE, name)
    assert has_atomic_decorator(node)
    assert_lock_before_validation(node, "validar_retiro_super_admin")


@pytest.mark.parametrize("name", ["update_user", "cambiar_estatus_usuario"])
def test_cambios_estatus_bloqueados_dentro_transaccion(name):
    node = function(SERVICE, name)
    assert_lock_before_validation(node, "validar_cambio_estatus_protegido")
    transactions = [n for n in ast.walk(node) if isinstance(n, ast.AsyncWith)
                    and any(isinstance(item.context_expr, ast.Call)
                            and isinstance(item.context_expr.func, ast.Name)
                            and item.context_expr.func.id == "in_transaction"
                            for item in n.items)]
    assert transactions, "Debe existir transacción para cambiar estatus"
    transaction = transactions[0]
    assert_lock_before_validation(transaction, "validar_cambio_estatus_protegido")
    calls = [name for _, name in calls_in_order(transaction)]
    assert "invalidar_sesiones_usuario" in calls
    assert "enviar_correo_cambio_estatus_usuario" not in calls


def test_inactividad_no_revierte_el_403_tras_revocar():
    node = function(SESSION, "validar_ultima_sesion_o_revocar")
    tx = [n for n in ast.walk(node) if isinstance(n, ast.AsyncWith) and any(
        isinstance(item.context_expr, ast.Call)
        and isinstance(item.context_expr.func, ast.Name)
        and item.context_expr.func.id == "in_transaction"
        for item in n.items)]
    assert len(tx) == 1
    tx_calls = [name for _, name in calls_in_order(tx[0])]
    assert tx_calls.index("revocar_accesos_usuario") < tx_calls.index("invalidar_sesiones_usuario")
    assert not any(isinstance(n, ast.Raise) for n in ast.walk(tx[0]))
    assert any(isinstance(n, ast.Raise) and n.lineno > tx[0].end_lineno for n in ast.walk(node))


def test_revocacion_inactividad_adquiere_bloqueo_antes_de_verificacion():
    node = function(SESSION, "revocar_accesos_usuario")
    assert has_atomic_decorator(node)
    assert_lock_before_validation(node, "validar_revocacion_total_por_inactividad")


def test_bloqueo_no_requiere_tablas_nuevas():
    node = function(GUARD, "bloquear_mutacion_super_admin")
    text = ast.unparse(node)
    assert "select_for_update(no_key=True)" in text
    assert "EstatusUsuario" in text
