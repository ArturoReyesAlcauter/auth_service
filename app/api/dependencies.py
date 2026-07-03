from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import InvalidTokenError

from app.core.security import decode_access_token
from app.models.user import User, UsuarioAccion


bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        token_version_in_jwt: int | None = payload.get("token_version")
        token_type: str | None = payload.get("type")

        if user_id is None or token_version_in_jwt is None or token_type != "access":
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception
    except Exception:
        raise credentials_exception

    user = await User.get_or_none(id=user_id).prefetch_related(
        "estatus",
        "instancia",
    )

    if user is None:
        raise credentials_exception

    # Si las versiones no coinciden, el token fue invalidado prematuramente
    if user.token_version != token_version_in_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Esta sesión ha sido revocada por cambios en la cuenta. Por favor, inicia sesión de nuevo.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.estatus:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no tiene estatus asignado.",
        )

    if current_user.estatus.nombre.lower() != "activo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario no está activo.",
        )

    return current_user


def requiere_accion(nombre_accion: str) -> Callable:
    async def validar_permiso(
        # Solicitamos el token crudo desde el esquema de seguridad
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        # Validamos que el usuario exista y esté activo en DB
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        
        # Extraemos el payload decodificando el token.
        # Al ser solo una operación criptográfica en memoria, es ultrarrápida (0 hits a la DB).
        try:
            payload = decode_access_token(credentials.credentials)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido al validar permisos.",
            )

        # Obtenemos la lista de acciones del payload. Si no existe, devuelve una lista vacía.
        acciones_usuario = payload.get("acciones", [])

        # Validamos en memoria si la acción requerida está en la lista del token
        if nombre_accion not in acciones_usuario:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes permiso para ejecutar la acción: {nombre_accion}",
            )

        return current_user

    return validar_permiso