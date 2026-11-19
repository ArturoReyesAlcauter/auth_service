"""Contratos estructurales del Lote 3 que no requieren PostgreSQL."""
import ast
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[2] / "app" / "services" / "user_service.py"


def _functions():
    module = ast.parse(SERVICE.read_text(encoding="utf-8"))
    return {node.name: node for node in module.body if isinstance(node, ast.AsyncFunctionDef)}


def test_persistencia_masiva_es_atomica_y_envio_externo_no():
    funcs = _functions()
    interior = funcs["_assign_user_permisos_masivos_en_transaccion"]
    exterior = funcs["assign_user_permisos_masivos"]
    assert any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name)
               and d.func.id == "atomic" for d in interior.decorator_list)
    assert not exterior.decorator_list
    internos = {call.func.id for call in ast.walk(interior) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
    externos = {call.func.id for call in ast.walk(exterior) if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)}
    assert "enviar_correo_activacion_usuario" not in internos
    assert "generar_token_creacion_password" in internos
    assert "enviar_correo_activacion_usuario" in externos


def test_interior_bloquea_usuario_y_no_cambia_firma_publica():
    funcs = _functions()
    interior = funcs["_assign_user_permisos_masivos_en_transaccion"]
    exterior = funcs["assign_user_permisos_masivos"]
    args = [arg.arg for arg in exterior.args.args]
    assert args == ["user_id", "data", "current_user_id"]
    src = ast.unparse(interior)
    assert "select_for_update()" in src
