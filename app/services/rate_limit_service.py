from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status


# Diccionario en memoria:
# clave -> lista de fechas de intentos
_rate_limit_store: dict[str, list[datetime]] = {}


def _ahora():
    return datetime.now(timezone.utc)


def verificar_rate_limit(
    key: str,
    max_intentos: int,
    ventana_segundos: int,
    mensaje: str = "Demasiadas solicitudes. Intenta de nuevo más tarde.",
):
    """
    Rate limit simple en memoria.

    key:
    - Puede ser por IP
    - Puede ser por CURP
    - Puede ser por user_id

    max_intentos:
    - Número máximo de intentos permitidos dentro de la ventana.

    ventana_segundos:
    - Tiempo de ventana en segundos.
    """

    ahora = _ahora()
    limite_tiempo = ahora - timedelta(seconds=ventana_segundos)

    intentos = _rate_limit_store.get(key, [])

    # Quitamos intentos viejos fuera de la ventana
    intentos_recientes = [
        intento for intento in intentos
        if intento > limite_tiempo
    ]

    if len(intentos_recientes) >= max_intentos:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=mensaje,
        )

    intentos_recientes.append(ahora)
    _rate_limit_store[key] = intentos_recientes