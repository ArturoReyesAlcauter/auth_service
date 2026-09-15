from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class SemaforoModuleSpec:
    nombre: str
    descripcion: str
    acciones: Mapping[str, str]


@dataclass(frozen=True)
class SemaforoGroupSpec:
    descripcion: str
    modulos: tuple[SemaforoModuleSpec, ...]


ACCIONES_SEMAFORO_CRUD = MappingProxyType(
    {
        "VER_ACCIONES_SEMAFORO": (
            "Permite visualizar las acciones de su respectiva DG."
        ),
        "CREAR_ACCION_SEMAFORO": (
            "Permite crear una nueva acción en el semáforo."
        ),
        "EDITAR_ACCION_SEMAFORO": (
            "Permite editar las acciones pertenecientes a su DG."
        ),
        "ELIMINAR_ACCION_SEMAFORO": (
            "Permite eliminar lógicamente una acción."
        ),
    }
)

ACCIONES_SEMAFORO_DASHBOARD = MappingProxyType(
    {
        "VER_DASHBOARD_SEMAFORO": (
            "Permite consultar las estadísticas del semáforo."
        ),
    }
)

ACCIONES_SEMAFORO_ADMIN = MappingProxyType(
    {
        "ADMINISTRAR_TODO_SEMAFORO": (
            "Permite consultar, editar y supervisar los registros de todas "
            "las DGs en el Semáforo."
        ),
    }
)

SEMAFORO_ADMIN_GROUP = "SEMAFORO_ADMIN"
SEMAFORO_DG_GROUPS = (
    "SEMAFORO_DGRJRDNNA",
    "SEMAFORO_DGRCAS",
    "SEMAFORO_DGNPDDNNA",
    "SEMAFORO_DGCP",
)
SEMAFORO_GROUP_NAMES = (SEMAFORO_ADMIN_GROUP, *SEMAFORO_DG_GROUPS)

SEMAFORO_CONSOLIDATED_GROUP = "SEMAFORO"

SEMAFORO_GROUP_DESCRIPTIONS = MappingProxyType(
    {
        "SEMAFORO_ADMIN": "Administración y Supervisión Global del Semáforo",
        "SEMAFORO_DGRJRDNNA": (
            "Dirección General de Regulación, Jurisdicción y Restitución "
            "de Derechos de NNA"
        ),
        "SEMAFORO_DGRCAS": (
            "Dirección General de Representación Jurídica y Restitución de NNA"
        ),
        "SEMAFORO_DGNPDDNNA": (
            "Dirección General de Normatividad, Promoción y Difusión de los "
            "Derechos de NNA"
        ),
        "SEMAFORO_DGCP": "Dirección General de Coordinación y Políticas",
    }
)

DG_MODULES = (
    SemaforoModuleSpec(
        nombre="GESTION_ACCIONES",
        descripcion="Gestión del CRUD de Semáforo",
        acciones=ACCIONES_SEMAFORO_CRUD,
    ),
    SemaforoModuleSpec(
        nombre="DASHBOARD_SEMAFORO",
        descripcion="Estadísticas del Semáforo",
        acciones=ACCIONES_SEMAFORO_DASHBOARD,
    ),
)

ADMIN_MODULES = (
    SemaforoModuleSpec(
        nombre="CONTROL_GLOBAL_SEMAFORO",
        descripcion="Supervisión total del Semáforo",
        acciones=ACCIONES_SEMAFORO_ADMIN,
    ),
)

SEMAFORO_CATALOG: Mapping[str, SemaforoGroupSpec] = MappingProxyType(
    {
        SEMAFORO_ADMIN_GROUP: SemaforoGroupSpec(
            descripcion=SEMAFORO_GROUP_DESCRIPTIONS[SEMAFORO_ADMIN_GROUP],
            modulos=ADMIN_MODULES,
        ),
        **{
            group_name: SemaforoGroupSpec(
                descripcion=SEMAFORO_GROUP_DESCRIPTIONS[group_name],
                modulos=DG_MODULES,
            )
            for group_name in SEMAFORO_DG_GROUPS
        },
    }
)

ACTION_TO_MODULE = MappingProxyType(
    {
        **{name: "GESTION_ACCIONES" for name in ACCIONES_SEMAFORO_CRUD},
        **{name: "DASHBOARD_SEMAFORO" for name in ACCIONES_SEMAFORO_DASHBOARD},
        **{name: "CONTROL_GLOBAL_SEMAFORO" for name in ACCIONES_SEMAFORO_ADMIN},
    }
)


def target_group_for_consolidated_module(module_name: str) -> str | None:
    """Mapea un módulo creado por be092e9 hacia el grupo técnico de Agenda."""

    if module_name in SEMAFORO_GROUP_NAMES:
        return module_name
    return None
