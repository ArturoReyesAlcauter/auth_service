import unittest
from app.services.agenda_response import build_agenda_system_accesses

def group(name, *modules):
    return {"nombre": name, "modulos": [
        {"nombre": key, "acciones": [{"nombre": action} for action in actions]}
        for key, actions in modules
    ]}

class AgendaResponseTests(unittest.TestCase):
    def test_dg_is_exposed_with_valid_action(self):
        actual = build_agenda_system_accesses({"grupos": [group("SEMAFORO", ("SEMAFORO_DGCP", ["VER_ACCIONES_SEMAFORO"]))]})
        self.assertEqual(actual, [{"codigo": "CONTROL_AGENDA_NACIONAL", "grupos_autorizados": ["SEMAFORO"]}])

    def test_empty_admin_group_does_not_create_access(self):
        self.assertEqual(build_agenda_system_accesses({"grupos": [group("SEMAFORO", ("SEMAFORO_ADMIN", []))]}), [])

    def test_wrong_module_does_not_create_access(self):
        self.assertEqual(build_agenda_system_accesses({"grupos": [group("SEMAFORO", ("GESTION_ACCIONES", ["VER_ACCIONES_SEMAFORO"]))]}), [])

    def test_multiple_directions(self):
        actual = build_agenda_system_accesses({"grupos": [group("SEMAFORO",
            ("SEMAFORO_DGCP", ["VER_ACCIONES_SEMAFORO"]),
            ("SEMAFORO_DGRCAS", ["VER_DASHBOARD_SEMAFORO"]))]})
        self.assertEqual(actual[0]["grupos_autorizados"], ["SEMAFORO"])

    def test_rejects_legacy_group(self):
        self.assertEqual(build_agenda_system_accesses({"grupos": [group("SEMAFORO_DGCP", ("GESTION_ACCIONES", ["VER_ACCIONES_SEMAFORO"]))]}), [])

    def test_fails_closed_for_malformed_tree(self):
        for malformed in (None, [], {}, {"grupos": "SEMAFORO"}):
            with self.subTest(tree=malformed):
                self.assertEqual(build_agenda_system_accesses(malformed), [])

    def test_mesa_ayuda_does_not_create_agenda(self):
        self.assertEqual(build_agenda_system_accesses({"grupos": [group("MESA_AYUDA", ("BITACORA_ATENCIONES", ["VER_BITACORA"]))]}), [])


if __name__ == "__main__":
    unittest.main()
