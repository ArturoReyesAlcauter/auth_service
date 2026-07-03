from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


STATUS_DEFAULT_CODES = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_409_CONFLICT: "CONFLICT",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
    status.HTTP_429_TOO_MANY_REQUESTS: "TOO_MANY_REQUESTS",
}


def _normalize_error_detail(exc: HTTPException) -> dict:
    """
    Estandariza errores para frontend.

    Permite lanzar HTTPException con:
    - detail="Mensaje simple"
    - detail={"code": "TOKEN_EXPIRED", "detail": "Mensaje"}
    """
    if isinstance(exc.detail, dict):
        return {
            "code": exc.detail.get("code") or STATUS_DEFAULT_CODES.get(exc.status_code, "HTTP_ERROR"),
            "detail": exc.detail.get("detail") or exc.detail.get("message") or "Error en la solicitud.",
        }

    return {
        "code": STATUS_DEFAULT_CODES.get(exc.status_code, "HTTP_ERROR"),
        "detail": exc.detail or "Error en la solicitud.",
    }


async def http_exception_handler(request: Request, exc: HTTPException):
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=_normalize_error_detail(exc),
        headers=headers,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "detail": "La petición no cumple con el formato esperado.",
            "errors": exc.errors(),
        },
    )
