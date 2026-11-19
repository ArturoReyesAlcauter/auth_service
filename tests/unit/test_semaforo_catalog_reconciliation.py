"""Regresión del catálogo canónico: las DG son módulos, no grupos legados.

Este archivo sustituye pruebas del esquema SEMAFORO_* previo a la consolidación R4.
No restaurar ACTION_TO_MODULE ni grupos antiguos como solución al ImportError.
"""

from app.services.semaforo_catalog import (
    ACCIONES_SEMAFORO_ADMIN,
    ACCIONES_SEMAFORO_CRUD,
    ACCIONES_SEMAFORO_DASHBOARD,
    SEMAFORO_ADMIN_MODULE,
    SEMAFORO_CATALOG,
    SEMAFORO_CONSOLIDATED_GROUP,
    SEMAFORO_DG_MODULES,
)


def _modules():
    assert tuple(SEMAFORO_CATALOG) == (SEMAFORO_CONSOLIDATED_GROUP,)
    return {
        module.nombre: module
        for module in SEMAFORO_CATALOG[SEMAFORO_CONSOLIDATED_GROUP].modulos
    }


def test_legacy_group_names_are_modules_not_independent_groups():
    modules = _modules()
    assert set(modules) == {SEMAFORO_ADMIN_MODULE, *SEMAFORO_DG_MODULES}
    assert SEMAFORO_ADMIN_MODULE not in SEMAFORO_CATALOG
    assert all(name not in SEMAFORO_CATALOG for name in SEMAFORO_DG_MODULES)


def test_admin_action_is_only_in_admin_module():
    modules = _modules()
    admin_actions = set(ACCIONES_SEMAFORO_ADMIN)
    assert admin_actions == {"ADMINISTRAR_TODO_SEMAFORO"}
    assert set(modules[SEMAFORO_ADMIN_MODULE].acciones) == admin_actions
    for name in SEMAFORO_DG_MODULES:
        assert not admin_actions.intersection(modules[name].acciones)


def test_dg_modules_contain_crud_and_dashboard_without_admin_grants():
    modules = _modules()
    expected = set(ACCIONES_SEMAFORO_CRUD) | set(ACCIONES_SEMAFORO_DASHBOARD)
    assert len(expected) == 5
    for name in SEMAFORO_DG_MODULES:
        assert set(modules[name].acciones) == expected


def test_catalog_exposes_immutable_action_mappings():
    modules = _modules()
    try:
        modules[SEMAFORO_ADMIN_MODULE].acciones["PRUEBA"] = "No permitido"
    except TypeError:
        pass
    else:
        raise AssertionError("El catálogo de acciones debe ser inmutable")
