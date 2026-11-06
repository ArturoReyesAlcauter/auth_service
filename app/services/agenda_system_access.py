from __future__ import annotations

from app.services.semaforo_catalog import (
    SEMAFORO_CATALOG,
    SEMAFORO_CONSOLIDATED_GROUP,
)

AGENDA_SYSTEM_CODE = "CONTROL_AGENDA_NACIONAL"


def derive_agenda_system_access(grupos: object) -> dict | None:
    """Acceso efectivo: grupo SEMAFORO + módulo y acción del catálogo.

    Nunca confiere acceso por membresía sola, ni interpreta grupos SEMAFORO_*
    como grupos. Los nombres SEMAFORO_* solo son módulos del grupo principal.
    """
    if not isinstance(grupos, list):
        return None

    spec = SEMAFORO_CATALOG[SEMAFORO_CONSOLIDATED_GROUP]
    allowed_modules = {module.nombre: module.acciones for module in spec.modulos}

    for group in grupos:
        if not isinstance(group, dict) or group.get("nombre") != SEMAFORO_CONSOLIDATED_GROUP:
            continue

        modules = group.get("modulos")
        if not isinstance(modules, list):
            continue

        for module in modules:
            if not isinstance(module, dict):
                continue
            allowed = allowed_modules.get(module.get("nombre")) if isinstance(module.get("nombre"), str) else None
            actions = module.get("acciones")
            if allowed is None or not isinstance(actions, list):
                continue
            if any(
                isinstance(action, dict)
                and isinstance(action.get("nombre"), str)
                and action["nombre"] in allowed
                for action in actions
            ):
                return {
                    "codigo": AGENDA_SYSTEM_CODE,
                    "grupos_autorizados": [SEMAFORO_CONSOLIDATED_GROUP],
                }

    return None
