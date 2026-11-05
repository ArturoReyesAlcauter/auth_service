from __future__ import annotations

from app.services.agenda_system_access import derive_agenda_system_access


def build_agenda_system_accesses(permisos: object) -> list[dict]:
    """Expose only effective, catalog-validated Agenda access from Auth permissions.

    Fail closed if the permission tree has an unexpected structure; never create
    aliases, administrative grants or mutate stored permissions.
    """
    if not isinstance(permisos, dict):
        return []

    access = derive_agenda_system_access(permisos.get("grupos"))
    return [access] if access is not None else []
