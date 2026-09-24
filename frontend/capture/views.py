"""
Vistas de captura de cámara y consumo de la API de reconocimiento facial.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .services import FastAPIError, get_me, recognize_face, register_face


@login_required
def capture_view(request):
    """
    Página principal: muestra el feed de la cámara (getUserMedia) y los
    botones para registrar el rostro del usuario autenticado o para
    reconocer el rostro capturado contra los ya registrados.

    El botón de registro se oculta si el usuario ya tiene un rostro
    registrado (cada cuenta solo puede registrar su rostro una vez); esto
    es solo para la UI, el backend rechaza el endpoint de todas formas.
    """
    token = request.session.get("fastapi_token")
    has_token = bool(token)
    face_registered = False

    if has_token:
        try:
            me = get_me(token)
            face_registered = bool(me.get("has_face_registered"))
        except FastAPIError:
            # Si no se pudo consultar, se deja el botón visible: el
            # backend es quien realmente decide si acepta el registro.
            pass

    return render(
        request,
        "capture/capture.html",
        {"has_token": has_token, "face_registered": face_registered},
    )


@login_required
@require_POST
def register_face_view(request):
    """
    Recibe la imagen capturada (JSON: {"image_base64": "..."}) desde el
    JavaScript del navegador y la reenvía al backend FastAPI, autenticando
    con el JWT guardado en la sesión de Django al momento del login.
    """
    token = request.session.get("fastapi_token")
    if not token:
        return JsonResponse(
            {"ok": False, "error": "No hay una sesión válida con el servicio de reconocimiento facial. Vuelve a iniciar sesión."},
            status=401,
        )

    try:
        body = json.loads(request.body)
        image_base64 = body["image_base64"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"ok": False, "error": "Payload inválido"}, status=400)

    try:
        result = register_face(image_base64, token)
    except FastAPIError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    return JsonResponse({"ok": True, **result})


@login_required
@require_POST
def recognize_face_view(request):
    """
    Recibe una imagen capturada y la reenvía a FastAPI /face/recognize
    (ese endpoint de FastAPI no exige JWT: podría reutilizarse desde una
    pantalla pública de "login con tu cara" si se desea en el futuro).
    """
    try:
        body = json.loads(request.body)
        image_base64 = body["image_base64"]
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"ok": False, "error": "Payload inválido"}, status=400)

    try:
        result = recognize_face(image_base64)
    except FastAPIError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=502)

    return JsonResponse({"ok": True, **result})
