"""Comando legado intencionalmente inhabilitado.

El reconciliador antiguo creaba grupos SEMAFORO_* independientes.
El catálogo vigente es SEMAFORO -> cinco módulos internos.
No realiza conexiones ni escrituras, incluso cuando se pasa --apply.
"""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comando retirado: no crea ni reconcilia grupos de Semáforo."
    )
    parser.add_argument("--apply", action="store_true", help="Retirado; siempre rechazado.")
    args = parser.parse_args()
    if args.apply:
        print("RECONCILIADOR_RETIRADO: --apply bloqueado; ninguna conexión a BD.")
        return 2
    print("RECONCILIADOR_RETIRADO: no ejecutar; utilizar auditoría canónica de SEMAFORO.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
