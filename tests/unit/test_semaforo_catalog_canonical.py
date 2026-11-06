import subprocess
import sys
import unittest
from pathlib import Path

from app.services.semaforo_catalog import SEMAFORO_CATALOG


class CanonicalCatalogTests(unittest.TestCase):
    def test_exact_group_and_modules(self):
        self.assertEqual(tuple(SEMAFORO_CATALOG), ("SEMAFORO",))
        modules = SEMAFORO_CATALOG["SEMAFORO"].modulos
        self.assertEqual({m.nombre for m in modules}, {
            "SEMAFORO_ADMIN", "SEMAFORO_DGRJRDNNA", "SEMAFORO_DGRCAS", "SEMAFORO_DGNPDDNNA", "SEMAFORO_DGCP"
        })
        self.assertEqual([len(m.acciones) for m in modules], [1, 5, 5, 5, 5])

    def test_retired_reconciler_rejects_apply(self):
        path = Path(__file__).resolve().parents[2] / "scripts" / "reconcile_semaforo_catalog.py"
        result = subprocess.run([sys.executable, str(path), "--apply"], capture_output=True, text=True, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bloqueado", result.stdout)
