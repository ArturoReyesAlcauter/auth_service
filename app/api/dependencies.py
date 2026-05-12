from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.core.security import decode_access_token
from app.models.user import User, UsuarioAccion


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")

        if user_id is None:
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

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Valida que el usuario esté activo.

    En el modelo nuevo ya no usamos is_active.
    Ahora usamos cat_estatus_usuarios.
    """
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
    """
    Dependencia dinámica para proteger endpoints por acción.

    Ejemplo:
        usuario = Depends(requiere_accion("CREAR_NNA"))
    """

    async def validar_permiso(
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        tiene_permiso = await UsuarioAccion.filter(
            usuario_id=current_user.id,
            accion__nombre=nombre_accion,
        ).exists()

        if not tiene_permiso:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes permiso para ejecutar la acción: {nombre_accion}",
            )

        return current_user

    return validar_permiso