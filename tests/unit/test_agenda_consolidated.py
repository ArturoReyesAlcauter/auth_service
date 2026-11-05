import unittest
from app.services.agenda_system_access import derive_agenda_system_access

def group(name, *modules):
    return {"nombre": name, "modulos": [
        {"nombre": key, "acciones": [{"nombre": action} for action in actions]}
        for key, actions in modules
    ]}

class SemaforoConsolidatedAccessTests(unittest.TestCase):
    def test_canonical_dg_with_action(self):
        result = derive_agenda_system_access([group("SEMAFORO", ("SEMAFORO_DGCP", ["VER_ACCIONES_SEMAFORO"]))])
        self.assertEqual(result["grupos_autorizados"], ["SEMAFORO"])

    def test_empty_and_wrong_module_deny(self):
        self.assertIsNone(derive_agenda_system_access([group("SEMAFORO",
            ("SEMAFORO_DGCP", []), ("GESTION_ACCIONES", ["VER_ACCIONES_SEMAFORO"]))]))

    def test_admin_action_in_wrong_module_deny(self):
        self.assertIsNone(derive_agenda_system_access([group("SEMAFORO",
            ("SEMAFORO_DGCP", ["ADMINISTRAR_TODO_SEMAFORO"]))]))

    def test_legacy_rejected(self):
        self.assertIsNone(derive_agenda_system_access([group("SEMAFORO_DGCP",
            ("GESTION_ACCIONES", ["VER_ACCIONES_SEMAFORO"]))]))
