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


# Un solo grupo en el catálogo. Los nombres SEMAFORO_* son módulos, NO grupos.
SEMAFORO_CONSOLIDATED_GROUP = "SEMAFORO"
SEMAFORO_ADMIN_MODULE = "SEMAFORO_ADMIN"  # nombre del módulo administrativo
SEMAFORO_DG_MODULES = (
    "SEMAFORO_DGRJRDNNA",
    "SEMAFORO_DGRCAS",
    "SEMAFORO_DGNPDDNNA",
    "SEMAFORO_DGCP",
)

ACCIONES_SEMAFORO_CRUD = MappingProxyType({
    "VER_ACCIONES_SEMAFORO": "Permite visualizar las acciones de su respectiva DG.",
    "CREAR_ACCION_SEMAFORO": "Permite crear una nueva acción en el semáforo.",
    "EDITAR_ACCION_SEMAFORO": "Permite editar las acciones pertenecientes a su DG.",
    "ELIMINAR_ACCION_SEMAFORO": "Permite eliminar lógicamente una acción.",
})
ACCIONES_SEMAFORO_DASHBOARD = MappingProxyType({
    "VER_DASHBOARD_SEMAFORO": "Permite consultar las estadísticas del semáforo.",
})
ACCIONES_SEMAFORO_ADMIN = MappingProxyType({
    "ADMINISTRAR_TODO_SEMAFORO": (
        "Permite consultar, editar y supervisar los registros de todas "
        "las DGs en el Semáforo."
    ),
})

SEMAFORO_MODULE_DESCRIPTIONS = MappingProxyType({
    "SEMAFORO_ADMIN": "Administración y Supervisión Global del Semáforo",
    "SEMAFORO_DGRJRDNNA": (
        "Dirección General de Regulación, Jurisdicción y Restitución de Derechos de NNA"
    ),
    "SEMAFORO_DGRCAS": "Dirección General de Representación Jurídica y Restitución de NNA",
    "SEMAFORO_DGNPDDNNA": (
        "Dirección General de Normatividad, Promoción y Difusión de los Derechos de NNA"
    ),
    "SEMAFORO_DGCP": "Dirección General de Coordinación y Políticas",
})

SEMAFORO_CATALOG: Mapping[str, SemaforoGroupSpec] = MappingProxyType({
    SEMAFORO_CONSOLIDATED_GROUP: SemaforoGroupSpec(
        descripcion="Control Agenda Nacional (Semáforo)",
        modulos=(
            SemaforoModuleSpec(
                nombre=SEMAFORO_ADMIN_MODULE,
                descripcion=SEMAFORO_MODULE_DESCRIPTIONS[SEMAFORO_ADMIN_MODULE],
                acciones=ACCIONES_SEMAFORO_ADMIN,
            ),
            *(
                SemaforoModuleSpec(
                    nombre=name,
                    descripcion=SEMAFORO_MODULE_DESCRIPTIONS[name],
                    acciones=MappingProxyType({
                        **ACCIONES_SEMAFORO_CRUD,
                        **ACCIONES_SEMAFORO_DASHBOARD,
                    }),
                )
                for name in SEMAFORO_DG_MODULES
            ),
        ),
    ),
})
