"""
Cliente HTTP hacia los endpoints de reconocimiento facial del backend FastAPI.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)
TIMEOUT = 15  # el análisis de imagen puede tardar un poco más que un login


class FastAPIError(Exception):
    pass


def _parse_json(resp: requests.Response) -> dict:
    """Ver accounts.services._parse_json: evita que un error 500 en texto
    plano del backend tumbe la vista de Django con un JSONDecodeError."""
    try:
        return resp.json()
    except ValueError:
        logger.error(
            "Respuesta no-JSON del backend FastAPI (status %s): %s",
            resp.status_code,
            resp.text[:300],
        )
        raise FastAPIError(
            f"El backend respondió de forma inesperada (código {resp.status_code}). "
            "Revisa la terminal donde corre 'uvicorn' para ver el error real."
        )


def get_me(token: str) -> dict:
    """
    Consulta el estado actual del usuario autenticado en el backend
    FastAPI (incluye `has_face_registered`), para saber si ya tiene un
    rostro registrado y así ocultar/deshabilitar el registro en la UI
    (el backend igual lo rechaza aunque alguien se salte esta consulta).
    """
    try:
        resp = requests.get(
            f"{settings.FASTAPI_BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Fallo al contactar FastAPI /auth/me: %s", exc)
        raise FastAPIError("No se pudo contactar el servicio de reconocimiento facial") from exc

    data = _parse_json(resp)
    if resp.status_code >= 400:
        raise FastAPIError(data.get("detail", "No se pudo consultar el estado del usuario"))
    return data


def register_face(image_base64: str, token: str) -> dict:
    try:
        resp = requests.post(
            f"{settings.FASTAPI_BASE_URL}/face/register",
            json={"image_base64": image_base64},
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Fallo al contactar FastAPI /face/register: %s", exc)
        raise FastAPIError("No se pudo contactar el servicio de reconocimiento facial") from exc

    data = _parse_json(resp)
    if resp.status_code >= 400:
        raise FastAPIError(data.get("detail", "No se pudo registrar el rostro"))
    return data


def recognize_face(image_base64: str) -> dict:
    try:
        resp = requests.post(
            f"{settings.FASTAPI_BASE_URL}/face/recognize",
            json={"image_base64": image_base64},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("Fallo al contactar FastAPI /face/recognize: %s", exc)
        raise FastAPIError("No se pudo contactar el servicio de reconocimiento facial") from exc

    data = _parse_json(resp)
    if resp.status_code >= 400:
        raise FastAPIError(data.get("detail", "No se pudo procesar la imagen"))
    return data
