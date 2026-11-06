import unittest

from app.services.agenda_system_access import AGENDA_SYSTEM_CODE, derive_agenda_system_access
from app.services.semaforo_catalog import SEMAFORO_CATALOG


def group(name, *modules):
    return {"nombre": name, "modulos": [
        {"nombre": key, "acciones": [{"nombre": action} for action in actions]}
        for key, actions in modules
    ]}

class AgendaSystemAccessTests(unittest.TestCase):
    def test_catalog_has_one_group_five_modules_21_actions(self):
        self.assertEqual(set(SEMAFORO_CATALOG), {"SEMAFORO"})
        modules = SEMAFORO_CATALOG["SEMAFORO"].modulos
        self.assertEqual(len(modules), 5)
        self.assertEqual(sum(len(module.acciones) for module in modules), 21)

    def test_valid_dg_access(self):
        result = derive_agenda_system_access([group("SEMAFORO",
            ("SEMAFORO_DGCP", ["VER_ACCIONES_SEMAFORO"]))])
        self.assertEqual(result, {"codigo": AGENDA_SYSTEM_CODE, "grupos_autorizados": ["SEMAFORO"]})

    def test_valid_admin_action(self):
        self.assertIsNotNone(derive_agenda_system_access([group("SEMAFORO",
            ("SEMAFORO_ADMIN", ["ADMINISTRAR_TODO_SEMAFORO"]))]))

    def test_empty_or_malformed_deny(self):
        for invalid in (None, {}, [], [group("SEMAFORO")],
                        [{"nombre": "SEMAFORO", "modulos": "incorrecto"}]):
            with self.subTest(invalid=invalid):
                self.assertIsNone(derive_agenda_system_access(invalid))

    def test_wrong_module_action_denied(self):
        for module, action in (
            ("GESTION_ACCIONES", "VER_ACCIONES_SEMAFORO"),
            ("SEMAFORO_DGCP", "ADMINISTRAR_TODO_SEMAFORO"),
            ("SEMAFORO_ADMIN", "VER_ACCIONES_SEMAFORO"),
            ("SEMAFORO_DGRCAS", "SUPER_ADMIN"),
        ):
            with self.subTest(module=module, action=action):
                self.assertIsNone(derive_agenda_system_access([group("SEMAFORO", (module, [action]))]))

    def test_old_groups_do_not_grant_access(self):
        for name in ("SEMAFORO_ADMIN", "SEMAFORO_DGRJRDNNA", "SEMAFORO_DGRCAS", "SEMAFORO_DGNPDDNNA", "SEMAFORO_DGCP"):
            with self.subTest(name=name):
                self.assertIsNone(derive_agenda_system_access([group(name, ("GESTION_ACCIONES", ["VER_ACCIONES_SEMAFORO"]))]))

    def test_multiple_dg_modules_in_one_group(self):
        result = derive_agenda_system_access([group("SEMAFORO",
            ("SEMAFORO_DGCP", ["CREAR_ACCION_SEMAFORO"]),
            ("SEMAFORO_DGRCAS", ["VER_DASHBOARD_SEMAFORO"]))])
        self.assertEqual(result["grupos_autorizados"], ["SEMAFORO"])

    def test_mesa_no_acceso(self):
        self.assertIsNone(derive_agenda_system_access([group("MESA_AYUDA", ("BITACORA_ATENCIONES", ["VER_BITACORA"]))]))


if __name__ == "__main__":
    unittest.main()
