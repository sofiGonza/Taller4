"""
Cliente HTTP hacia el backend FastAPI para las operaciones de cuenta.

Django mantiene su propia sesión (django.contrib.auth) para proteger las
vistas del sitio, y además sincroniza cada usuario con el backend FastAPI
para poder usar sus endpoints de reconocimiento facial (que requieren un
JWT propio). El token de FastAPI se guarda en `request.session`.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 8  # segundos


class FastAPIError(Exception):
    """Error de comunicación o de negocio al hablar con el backend FastAPI."""


def _parse_json(resp: requests.Response) -> dict:
    """
    Intenta leer la respuesta como JSON. Si el backend devolvió algo que no
    es JSON (por ejemplo un error 500 en texto plano por una excepción no
    controlada), no se deja propagar el error de parseo: se convierte en un
    FastAPIError con un mensaje entendible, incluyendo un fragmento de la
    respuesta cruda para poder diagnosticar el problema real.
    """
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


def register_user(username: str, email: str, password: str) -> dict:
    try:
        resp = requests.post(
            f"{settings.FASTAPI_BASE_URL}/auth/register",
            json={"username": username, "email": email or None, "password": password},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo contactar al backend FastAPI: %s", exc)
        raise FastAPIError("El servicio de reconocimiento facial no está disponible ahora mismo") from exc

    data = _parse_json(resp)
    if resp.status_code >= 400:
        raise FastAPIError(data.get("detail", "No se pudo registrar el usuario en la API"))
    return data


def login_user(username: str, password: str) -> str:
    """Devuelve el access_token JWT del backend FastAPI."""
    try:
        resp = requests.post(
            f"{settings.FASTAPI_BASE_URL}/auth/login",
            data={"username": username, "password": password},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("No se pudo contactar al backend FastAPI: %s", exc)
        raise FastAPIError("El servicio de reconocimiento facial no está disponible ahora mismo") from exc

    data = _parse_json(resp)
    if resp.status_code >= 400:
        raise FastAPIError(data.get("detail", "No se pudo iniciar sesión en la API"))
    return data["access_token"]
