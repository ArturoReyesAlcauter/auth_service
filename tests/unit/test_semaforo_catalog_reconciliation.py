import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.semaforo_catalog import (
    ACTION_TO_MODULE,
    SEMAFORO_ADMIN_GROUP,
    SEMAFORO_CATALOG,
    SEMAFORO_DG_GROUPS,
    SEMAFORO_GROUP_NAMES,
    target_group_for_consolidated_module,
)


def test_semaforo_technical_names_are_groups() -> None:
    assert tuple(SEMAFORO_CATALOG) == SEMAFORO_GROUP_NAMES
    assert SEMAFORO_ADMIN_GROUP == "SEMAFORO_ADMIN"
    assert set(SEMAFORO_DG_GROUPS) == {
        "SEMAFORO_DGRJRDNNA",
        "SEMAFORO_DGRCAS",
        "SEMAFORO_DGNPDDNNA",
        "SEMAFORO_DGCP",
    }


def test_admin_group_has_global_control_module() -> None:
    modules = SEMAFORO_CATALOG[SEMAFORO_ADMIN_GROUP].modulos
    assert [module.nombre for module in modules] == ["CONTROL_GLOBAL_SEMAFORO"]
    assert set(modules[0].acciones) == {"ADMINISTRAR_TODO_SEMAFORO"}


def test_dg_groups_have_crud_and_dashboard_modules() -> None:
    for group_name in SEMAFORO_DG_GROUPS:
        modules = SEMAFORO_CATALOG[group_name].modulos
        assert [module.nombre for module in modules] == [
            "GESTION_ACCIONES",
            "DASHBOARD_SEMAFORO",
        ]
        assert set(modules[0].acciones) == {
            "VER_ACCIONES_SEMAFORO",
            "CREAR_ACCION_SEMAFORO",
            "EDITAR_ACCION_SEMAFORO",
            "ELIMINAR_ACCION_SEMAFORO",
        }
        assert set(modules[1].acciones) == {"VER_DASHBOARD_SEMAFORO"}


def test_consolidated_modules_map_back_to_agenda_groups() -> None:
    for group_name in SEMAFORO_GROUP_NAMES:
        assert target_group_for_consolidated_module(group_name) == group_name

    assert target_group_for_consolidated_module("SEMAFORO") is None
    assert target_group_for_consolidated_module("OTRO") is None


def test_actions_map_to_their_target_modules() -> None:
    assert ACTION_TO_MODULE["VER_ACCIONES_SEMAFORO"] == "GESTION_ACCIONES"
    assert ACTION_TO_MODULE["VER_DASHBOARD_SEMAFORO"] == "DASHBOARD_SEMAFORO"
    assert ACTION_TO_MODULE["ADMINISTRAR_TODO_SEMAFORO"] == "CONTROL_GLOBAL_SEMAFORO"
