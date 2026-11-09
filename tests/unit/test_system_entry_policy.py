import unittest
from fastapi import HTTPException

from app.services.system_entry_policy import has_system_access, require_system_entry, target_for_redirect


def perms(*groups):
    return {"grupos": list(groups)}


def group(name, *actions, module="MODULO"):
    return {"nombre": name, "modulos": [{"nombre": module, "acciones": [{"nombre": a} for a in actions]}]}


class EffectiveAuthorizationTests(unittest.TestCase):
    def test_super_admin_does_not_grant_mesa_or_formatos(self):
        data = perms(group("MESA_AYUDA", "SUPER_ADMIN"))
        self.assertTrue(has_system_access("ADMINISTRACION_SISTEMA", data))
        self.assertFalse(has_system_access("MESA_AYUDA", data))
        self.assertFalse(has_system_access("FORMATOS_ATENCIONES", data))
        self.assertFalse(has_system_access("DIRECTORIO_PROCURADORES", data))
        self.assertFalse(has_system_access("CONTROL_AGENDA_NACIONAL", data))

    def test_individual_actions_are_required(self):
        data = perms(group("MESA_AYUDA", "VER_BITACORA"))
        self.assertTrue(has_system_access("MESA_AYUDA", data))
        self.assertFalse(has_system_access("ADMINISTRACION_SISTEMA", data))

    def test_old_semaforo_groups_do_not_authorize(self):
        data = perms(group("SEMAFORO_DGCP", "CREAR_ACCION_SEMAFORO", module="GESTION_ACCIONES"))
        self.assertFalse(has_system_access("CONTROL_AGENDA_NACIONAL", data))

    def test_canonical_agenda_action_is_required(self):
        data = perms(group("SEMAFORO", "VER_ACCIONES_SEMAFORO", module="SEMAFORO_DGCP"))
        self.assertTrue(has_system_access("CONTROL_AGENDA_NACIONAL", data))

    def test_directorio_requires_explicit_membership(self):
        self.assertTrue(has_system_access("DIRECTORIO_PROCURADORES", perms(group("DIRECTORIO_PROCURADORES"))))
        self.assertFalse(has_system_access("DIRECTORIO_PROCURADORES", perms(group("MESA_AYUDA", "SUPER_ADMIN"))))

    def test_unknown_redirect_is_closed(self):
        self.assertIsNone(target_for_redirect("https://unmapped.example/app/dashboard"))
        with self.assertRaises(HTTPException) as err:
            require_system_entry("https://unmapped.example/app/dashboard", perms(group("MESA_AYUDA", "SUPER_ADMIN")))
        self.assertEqual(err.exception.status_code, 403)

    def test_revoked_user_cannot_generate_redirect_code(self):
        with self.assertRaises(HTTPException) as err:
            require_system_entry("https://mesa.pfpnna.tech/app/dashboard", perms(group("MESA_AYUDA", "SUPER_ADMIN")))
        self.assertEqual(err.exception.status_code, 403)
        self.assertEqual(err.exception.detail["code"], "SYSTEM_ACCESS_REVOKED")

    def test_explicit_mesa_permission_authorizes(self):
        require_system_entry("https://mesa.pfpnna.tech/app/dashboard", perms(group("MESA_AYUDA", "VER_BITACORA")))

    def test_legacy_semaforo_rejected(self):
        with self.assertRaises(HTTPException):
            require_system_entry("https://agenda.pfpnna.tech/app/dashboard", perms(group("SEMAFORO_DGCP", "VER_ACCIONES_SEMAFORO")))

    def test_admin_without_system_rights_cannot_access_mesa(self):
        with self.assertRaises(HTTPException):
            require_system_entry("https://mesa.pfpnna.tech/app/dashboard", perms(group("MESA_AYUDA", "ADMINISTRAR_USUARIOS")))

    def test_legacy_local_port_routes_not_confused(self):
        self.assertEqual(target_for_redirect("http://127.0.0.1:5173/app/formato-nna"), "FORMATOS_ATENCIONES")
        self.assertEqual(target_for_redirect("http://127.0.0.1:5173/app/usuarios"), "ADMINISTRACION_SISTEMA")
        self.assertEqual(target_for_redirect("http://127.0.0.1:5173/app/dashboard"), "MESA_AYUDA")
        self.assertIsNone(target_for_redirect("http://127.0.0.1:5173/unknown"))

    def test_domain_spoofing_is_rejected(self):
        self.assertIsNone(target_for_redirect("https://mesa.pfpnna.tech.attacker.invalid/app/dashboard"))
        self.assertIsNone(target_for_redirect("http://mesa.pfpnna.tech/app/dashboard"))
        self.assertIsNone(target_for_redirect("https://mesa.pfpnna.tech:444/app/dashboard"))


if __name__ == "__main__":
    unittest.main()
