from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable
from uuid import UUID

from tortoise import Tortoise
from tortoise.expressions import F
from tortoise.transactions import in_transaction

from app.core.config import TORTOISE_ORM
from app.models.user import (
    Accion,
    Grupo,
    Modulo,
    User,
    UsuarioAccion,
    UsuarioGrupo,
    UsuarioModulo,
)
from app.services.semaforo_catalog import (
    ACTION_TO_MODULE,
    SEMAFORO_ADMIN_GROUP,
    SEMAFORO_CATALOG,
    SEMAFORO_CONSOLIDATED_GROUP,
    target_group_for_consolidated_module,
)


@dataclass
class ReconciliationPlan:
    catalog_creates: list[str] = field(default_factory=list)
    catalog_updates: list[str] = field(default_factory=list)
    group_assignments: set[tuple[UUID, str]] = field(default_factory=set)
    module_assignments: set[tuple[UUID, str, str]] = field(default_factory=set)
    action_assignments: set[tuple[UUID, str, str, str]] = field(default_factory=set)
    users_to_invalidate: set[UUID] = field(default_factory=set)
    unresolved_group_only_users: set[UUID] = field(default_factory=set)
    unmapped_action_names: set[str] = field(default_factory=set)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.catalog_creates
            or self.catalog_updates
            or self.group_assignments
            or self.module_assignments
            or self.action_assignments
        )


async def _unique_group(name: str) -> Grupo | None:
    grupos = await Grupo.filter(nombre=name).all()
    if len(grupos) > 1:
        raise RuntimeError(
            f"Catálogo ambiguo: existen {len(grupos)} grupos con nombre {name}. "
            "No se aplicará ninguna reconciliación automática."
        )
    return grupos[0] if grupos else None


async def _unique_module(grupo: Grupo, name: str) -> Modulo | None:
    modulos = await Modulo.filter(grupo_id=grupo.id, nombre=name).all()
    if len(modulos) > 1:
        raise RuntimeError(
            f"Catálogo ambiguo: existen {len(modulos)} módulos {name} "
            f"dentro de {grupo.nombre}."
        )
    return modulos[0] if modulos else None


async def _unique_action(modulo: Modulo, name: str) -> Accion | None:
    acciones = await Accion.filter(modulo_id=modulo.id, nombre=name).all()
    if len(acciones) > 1:
        raise RuntimeError(
            f"Catálogo ambiguo: existen {len(acciones)} acciones {name} "
            f"dentro de {modulo.nombre}."
        )
    return acciones[0] if acciones else None


async def _catalog_objects() -> tuple[
    dict[str, Grupo | None],
    dict[tuple[str, str], Modulo | None],
    dict[tuple[str, str, str], Accion | None],
]:
    groups: dict[str, Grupo | None] = {}
    modules: dict[tuple[str, str], Modulo | None] = {}
    actions: dict[tuple[str, str, str], Accion | None] = {}

    for group_name, group_spec in SEMAFORO_CATALOG.items():
        group = await _unique_group(group_name)
        groups[group_name] = group

        for module_spec in group_spec.modulos:
            module = await _unique_module(group, module_spec.nombre) if group else None
            modules[(group_name, module_spec.nombre)] = module

            for action_name in module_spec.acciones:
                action = await _unique_action(module, action_name) if module else None
                actions[(group_name, module_spec.nombre, action_name)] = action

    return groups, modules, actions


async def _build_catalog_plan(plan: ReconciliationPlan) -> tuple[
    dict[str, Grupo | None],
    dict[tuple[str, str], Modulo | None],
    dict[tuple[str, str, str], Accion | None],
]:
    groups, modules, actions = await _catalog_objects()

    for group_name, group_spec in SEMAFORO_CATALOG.items():
        group = groups[group_name]
        if group is None:
            plan.catalog_creates.append(f"grupo:{group_name}")
        elif group.descripcion != group_spec.descripcion:
            plan.catalog_updates.append(f"grupo:{group_name}")

        for module_spec in group_spec.modulos:
            module_key = (group_name, module_spec.nombre)
            module = modules[module_key]
            if module is None:
                plan.catalog_creates.append(
                    f"modulo:{group_name}/{module_spec.nombre}"
                )
            elif module.descripcion != module_spec.descripcion:
                plan.catalog_updates.append(
                    f"modulo:{group_name}/{module_spec.nombre}"
                )

            for action_name, description in module_spec.acciones.items():
                action_key = (group_name, module_spec.nombre, action_name)
                action = actions[action_key]
                if action is None:
                    plan.catalog_creates.append(
                        f"accion:{group_name}/{module_spec.nombre}/{action_name}"
                    )
                elif action.descripcion != description:
                    plan.catalog_updates.append(
                        f"accion:{group_name}/{module_spec.nombre}/{action_name}"
                    )

    return groups, modules, actions


async def _build_assignment_plan(
    plan: ReconciliationPlan,
    groups: dict[str, Grupo | None],
    modules: dict[tuple[str, str], Modulo | None],
    actions: dict[tuple[str, str, str], Accion | None],
) -> None:
    consolidated_group = await _unique_group(SEMAFORO_CONSOLIDATED_GROUP)
    if consolidated_group is None:
        return

    wrong_modules = await Modulo.filter(grupo_id=consolidated_group.id).all()
    wrong_modules_by_id = {
        module.id: module
        for module in wrong_modules
        if target_group_for_consolidated_module(module.nombre)
    }

    if not wrong_modules_by_id:
        group_assignments = await UsuarioGrupo.filter(
            grupo_id=consolidated_group.id
        ).all()
        plan.unresolved_group_only_users.update(
            assignment.usuario_id for assignment in group_assignments
        )
        return

    wrong_module_ids = list(wrong_modules_by_id)
    module_assignments = await UsuarioModulo.filter(
        modulo_id__in=wrong_module_ids
    ).all()

    users_with_wrong_module: set[UUID] = set()

    for assignment in module_assignments:
        wrong_module = wrong_modules_by_id[assignment.modulo_id]
        target_group_name = target_group_for_consolidated_module(
            wrong_module.nombre
        )
        if target_group_name is None:
            continue

        user_id = assignment.usuario_id
        users_with_wrong_module.add(user_id)

        target_group = groups[target_group_name]
        group_exists = bool(
            target_group
            and await UsuarioGrupo.filter(
                usuario_id=user_id,
                grupo_id=target_group.id,
            ).exists()
        )
        if not group_exists:
            plan.group_assignments.add((user_id, target_group_name))
            plan.users_to_invalidate.add(user_id)

        target_module_names = (
            ("CONTROL_GLOBAL_SEMAFORO",)
            if target_group_name == SEMAFORO_ADMIN_GROUP
            else ("GESTION_ACCIONES", "DASHBOARD_SEMAFORO")
        )

        for target_module_name in target_module_names:
            target_module = modules[(target_group_name, target_module_name)]
            module_exists = bool(
                target_module
                and await UsuarioModulo.filter(
                    usuario_id=user_id,
                    modulo_id=target_module.id,
                ).exists()
            )
            if not module_exists:
                plan.module_assignments.add(
                    (user_id, target_group_name, target_module_name)
                )
                plan.users_to_invalidate.add(user_id)

    wrong_actions = await Accion.filter(modulo_id__in=wrong_module_ids).all()
    wrong_actions_by_id = {action.id: action for action in wrong_actions}

    if wrong_actions_by_id:
        action_assignments = await UsuarioAccion.filter(
            accion_id__in=list(wrong_actions_by_id)
        ).all()

        for assignment in action_assignments:
            old_action = wrong_actions_by_id[assignment.accion_id]
            wrong_module = wrong_modules_by_id.get(old_action.modulo_id)
            if wrong_module is None:
                continue

            target_group_name = target_group_for_consolidated_module(
                wrong_module.nombre
            )
            target_module_name = ACTION_TO_MODULE.get(old_action.nombre)

            if target_group_name is None or target_module_name is None:
                plan.unmapped_action_names.add(old_action.nombre)
                continue

            group_spec = SEMAFORO_CATALOG[target_group_name]
            target_module_spec = next(
                (
                    module_spec
                    for module_spec in group_spec.modulos
                    if module_spec.nombre == target_module_name
                ),
                None,
            )
            if (
                target_module_spec is None
                or old_action.nombre not in target_module_spec.acciones
            ):
                plan.unmapped_action_names.add(old_action.nombre)
                continue

            target_action = actions[
                (target_group_name, target_module_name, old_action.nombre)
            ]
            action_exists = bool(
                target_action
                and await UsuarioAccion.filter(
                    usuario_id=assignment.usuario_id,
                    accion_id=target_action.id,
                ).exists()
            )
            if not action_exists:
                plan.action_assignments.add(
                    (
                        assignment.usuario_id,
                        target_group_name,
                        target_module_name,
                        old_action.nombre,
                    )
                )
                plan.users_to_invalidate.add(assignment.usuario_id)

    consolidated_assignments = await UsuarioGrupo.filter(
        grupo_id=consolidated_group.id
    ).all()
    for assignment in consolidated_assignments:
        if assignment.usuario_id not in users_with_wrong_module:
            plan.unresolved_group_only_users.add(assignment.usuario_id)


async def build_plan() -> ReconciliationPlan:
    plan = ReconciliationPlan()
    groups, modules, actions = await _build_catalog_plan(plan)
    await _build_assignment_plan(plan, groups, modules, actions)
    return plan


async def _ensure_catalog(using_db) -> tuple[
    dict[str, Grupo],
    dict[tuple[str, str], Modulo],
    dict[tuple[str, str, str], Accion],
]:
    groups: dict[str, Grupo] = {}
    modules: dict[tuple[str, str], Modulo] = {}
    actions: dict[tuple[str, str, str], Accion] = {}

    for group_name, group_spec in SEMAFORO_CATALOG.items():
        group, _ = await Grupo.get_or_create(
            nombre=group_name,
            defaults={"descripcion": group_spec.descripcion},
            using_db=using_db,
        )
        if group.descripcion != group_spec.descripcion:
            group.descripcion = group_spec.descripcion
            await group.save(using_db=using_db, update_fields=["descripcion"])
        groups[group_name] = group

        for module_spec in group_spec.modulos:
            module, _ = await Modulo.get_or_create(
                grupo_id=group.id,
                nombre=module_spec.nombre,
                defaults={"descripcion": module_spec.descripcion},
                using_db=using_db,
            )
            if module.descripcion != module_spec.descripcion:
                module.descripcion = module_spec.descripcion
                await module.save(
                    using_db=using_db,
                    update_fields=["descripcion"],
                )
            modules[(group_name, module_spec.nombre)] = module

            for action_name, description in module_spec.acciones.items():
                action, _ = await Accion.get_or_create(
                    modulo_id=module.id,
                    nombre=action_name,
                    defaults={"descripcion": description},
                    using_db=using_db,
                )
                if action.descripcion != description:
                    action.descripcion = description
                    await action.save(
                        using_db=using_db,
                        update_fields=["descripcion"],
                    )
                actions[(group_name, module_spec.nombre, action_name)] = action

    return groups, modules, actions


async def apply_plan(plan: ReconciliationPlan) -> int:
    changed_users: set[UUID] = set()

    async with in_transaction() as connection:
        groups, modules, actions = await _ensure_catalog(connection)

        for user_id, group_name in sorted(
            plan.group_assignments,
            key=lambda item: (str(item[0]), item[1]),
        ):
            _, created = await UsuarioGrupo.get_or_create(
                usuario_id=user_id,
                grupo_id=groups[group_name].id,
                using_db=connection,
            )
            if created:
                changed_users.add(user_id)

        for user_id, group_name, module_name in sorted(
            plan.module_assignments,
            key=lambda item: (str(item[0]), item[1], item[2]),
        ):
            _, created = await UsuarioModulo.get_or_create(
                usuario_id=user_id,
                modulo_id=modules[(group_name, module_name)].id,
                using_db=connection,
            )
            if created:
                changed_users.add(user_id)

        for user_id, group_name, module_name, action_name in sorted(
            plan.action_assignments,
            key=lambda item: (str(item[0]), item[1], item[2], item[3]),
        ):
            _, created = await UsuarioAccion.get_or_create(
                usuario_id=user_id,
                accion_id=actions[(group_name, module_name, action_name)].id,
                using_db=connection,
            )
            if created:
                changed_users.add(user_id)

        if changed_users:
            await User.filter(id__in=list(changed_users)).using_db(connection).update(
                token_version=F("token_version") + 1
            )

    return len(changed_users)


def _print_items(title: str, items: Iterable[str]) -> None:
    items = list(items)
    print(f"{title}: {len(items)}")
    for item in items:
        print(f"  - {item}")


def print_plan(plan: ReconciliationPlan) -> None:
    print("=== RECONCILIACIÓN SEMÁFORO ===")
    _print_items("Catálogo a crear", sorted(plan.catalog_creates))
    _print_items("Catálogo a actualizar", sorted(plan.catalog_updates))
    print(f"Asignaciones de grupo a agregar: {len(plan.group_assignments)}")
    print(f"Asignaciones de módulo a agregar: {len(plan.module_assignments)}")
    print(f"Asignaciones de acción a agregar: {len(plan.action_assignments)}")
    print(f"Usuarios cuya sesión se invalidaría: {len(plan.users_to_invalidate)}")
    print(
        "Usuarios con grupo SEMAFORO sin módulo inferible: "
        f"{len(plan.unresolved_group_only_users)}"
    )
    if plan.unmapped_action_names:
        _print_items(
            "Acciones legacy sin mapeo automático",
            sorted(plan.unmapped_action_names),
        )
    print("El grupo consolidado SEMAFORO y sus asignaciones NO se eliminan.")


async def main(apply: bool) -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    try:
        plan = await build_plan()
        print_plan(plan)

        if not apply:
            print("DRY-RUN: no se escribió ningún cambio.")
            return

        affected = await apply_plan(plan)
        print(f"APPLY completado. Usuarios con sesión invalidada: {affected}")
        print(
            "No se realizaron DELETE. La estructura consolidada anterior queda "
            "preservada para una limpieza posterior, una vez validado Agenda."
        )
    finally:
        await Tortoise.close_connections()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcilia de forma aditiva el catálogo SEMAFORO_* requerido por "
            "Control Agenda Nacional. Sin --apply opera únicamente en dry-run."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica altas/actualizaciones aditivas y migra asignaciones inferibles.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(apply=args.apply))
